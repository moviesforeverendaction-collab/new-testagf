"""
ByteStreamer — pure MTProto media downloader.

One instance per MTProto client (dl_client or str_client).
Uses raw Telegram GetFile RPCs over a pool of authenticated DC sessions.

No session strings. No bot token. Just API_ID + API_HASH + MTProto.
"""
import asyncio
import contextlib
import logging
from collections import deque
from typing import AsyncGenerator, Dict

from pyrogram import Client, utils, raw
from pyrogram.errors import (
    AuthBytesInvalid,
    FileReferenceEmpty,
    FileReferenceExpired,
    FileReferenceInvalid,
)
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Auth, Session

from FileStream.config import Server
from .file_properties import get_file_ids

FILE_REF_ERRORS = (FileReferenceEmpty, FileReferenceExpired, FileReferenceInvalid)


class ByteStreamer:
    def __init__(self, client: Client, role: str):
        self.client = client
        self.role   = role          # "dl" or "stream" — for logging only
        self._file_cache: Dict[str, FileId] = {}
        self._pools:  Dict[int, list]             = {}  # dc_id → [Session]
        self._locks:  Dict[int, asyncio.Lock]     = {}
        asyncio.create_task(self._cache_cleaner())

    # ── File-ID cache ─────────────────────────────────────────────────────

    async def get_file_properties(
        self, db_id: str, multi_clients: dict, force_refresh: bool = False
    ) -> FileId:
        if force_refresh:
            self._file_cache.pop(db_id, None)
        if db_id not in self._file_cache:
            fid = await get_file_ids(self.client, db_id, multi_clients, force_refresh=force_refresh)
            if fid is None:
                raise RuntimeError(f"Cannot resolve file for db_id={db_id!r}")
            self._file_cache[db_id] = fid
        return self._file_cache[db_id]

    # ── DC session pool ───────────────────────────────────────────────────

    def _lock(self, dc_id: int) -> asyncio.Lock:
        if dc_id not in self._locks:
            self._locks[dc_id] = asyncio.Lock()
        return self._locks[dc_id]

    async def _new_session(self, file_id: FileId) -> Session:
        """Open one authenticated MTProto media session for file_id.dc_id."""
        client   = self.client
        own_dc   = await client.storage.dc_id()
        target   = file_id.dc_id
        test     = await client.storage.test_mode()

        if target != own_dc:
            session = Session(
                client, target,
                await Auth(client, target, test).create(),
                test, is_media=True,
            )
            await session.start()
            # Export/import auth so the foreign DC accepts our requests
            for _ in range(6):
                exported = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=target)
                )
                try:
                    await session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported.id, bytes=exported.bytes
                        )
                    )
                    break
                except AuthBytesInvalid:
                    continue
            else:
                await session.stop()
                raise AuthBytesInvalid
        else:
            session = Session(
                client, target,
                await client.storage.auth_key(),
                test, is_media=True,
            )
            await session.start()

        return session

    async def _get_pool(self, file_id: FileId) -> list:
        dc = file_id.dc_id
        if self._pools.get(dc):
            return self._pools[dc]

        async with self._lock(dc):
            if self._pools.get(dc):          # double-check
                return self._pools[dc]

            # Slot 0: reuse pyrogram's own cached session if available
            primary = self.client.media_sessions.get(dc)
            if primary is None:
                primary = await self._new_session(file_id)
                self.client.media_sessions[dc] = primary

            # Remaining slots created in parallel
            extras = await asyncio.gather(
                *[self._new_session(file_id) for _ in range(Server.MEDIA_SESSION_POOL_SIZE - 1)],
                return_exceptions=True,
            )
            pool = [primary] + [s for s in extras if isinstance(s, Session)]
            self._pools[dc] = pool
            logging.debug("[%s] DC %d pool ready: %d sessions", self.role, dc, len(pool))
            return pool

    async def _reset_pool(self, dc: int) -> None:
        pool   = self._pools.pop(dc, [])
        cached = self.client.media_sessions.pop(dc, None)
        seen   = {id(s): s for s in pool + ([cached] if cached else [])}
        for s in seen.values():
            with contextlib.suppress(Exception):
                await s.stop()

    # ── File location ─────────────────────────────────────────────────────

    @staticmethod
    def _make_location(file_id: FileId):
        ft = file_id.file_type
        if ft == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id,
                    access_hash=file_id.chat_access_hash,
                )
            elif file_id.chat_access_hash == 0:
                peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
            else:
                peer = raw.types.InputPeerChannel(
                    channel_id=utils.get_channel_id(file_id.chat_id),
                    access_hash=file_id.chat_access_hash,
                )
            return raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        if ft == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    # ── Core generator ────────────────────────────────────────────────────

    async def yield_file(
        self,
        db_id: str,
        multi_clients: dict,
        file_id: FileId,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ) -> AsyncGenerator[bytes, None]:
        retries   = Server.STREAM_MAX_RETRIES
        yielded   = 0
        cur_off   = offset
        cur_cut   = first_part_cut
        remaining = part_count

        while remaining > 0:
            pool     = await self._get_pool(file_id)
            location = self._make_location(file_id)
            n        = len(pool)

            pending: deque[asyncio.Task] = deque()
            next_off  = cur_off
            scheduled = 0
            part      = 1

            try:
                # Pre-fill the async pipeline
                prefill = min(Server.STREAM_PREFETCH, remaining, n * 2)
                while scheduled < prefill:
                    pending.append(asyncio.create_task(
                        _mtproto_get(pool[scheduled % n], location, next_off, chunk_size)
                    ))
                    next_off  += chunk_size
                    scheduled += 1

                # Drain + keep pipeline full
                while part <= remaining and pending:
                    resp = await pending.popleft()

                    if scheduled < remaining:
                        pending.append(asyncio.create_task(
                            _mtproto_get(pool[scheduled % n], location, next_off, chunk_size)
                        ))
                        next_off  += chunk_size
                        scheduled += 1

                    if not isinstance(resp, raw.types.upload.File):
                        raise RuntimeError("Unexpected MTProto response")

                    chunk = resp.bytes
                    if not chunk:
                        break

                    if remaining == 1:
                        yield chunk[cur_cut:last_part_cut]
                    elif part == 1:
                        yield chunk[cur_cut:]
                    elif part == remaining:
                        yield chunk[:last_part_cut]
                    else:
                        yield chunk

                    part    += 1
                    yielded += 1

                break  # done cleanly

            except FILE_REF_ERRORS:
                if retries <= 1:
                    raise
                logging.warning("[%s] File ref expired for %s, refreshing…", self.role, db_id)
                await self._reset_pool(file_id.dc_id)
                file_id   = await self.get_file_properties(db_id, multi_clients, force_refresh=True)
                cur_off  += (part - 1) * chunk_size
                remaining -= part - 1
                cur_cut    = 0 if yielded else cur_cut
                retries   -= 1

            except (TimeoutError, AttributeError, OSError, ConnectionError):
                if retries <= 1:
                    raise
                logging.warning("[%s] Transient error for %s, retrying…", self.role, db_id)
                await self._reset_pool(file_id.dc_id)
                cur_off  += (part - 1) * chunk_size
                remaining -= part - 1
                cur_cut    = 0 if yielded else cur_cut
                retries   -= 1

            finally:
                while pending:
                    t = pending.popleft()
                    if not t.done():
                        t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await t

    async def _cache_cleaner(self) -> None:
        while True:
            await asyncio.sleep(Server.FILE_ID_CACHE_TTL)
            self._file_cache.clear()
            logging.debug("[%s] file-ID cache cleared", self.role)


async def _mtproto_get(session: Session, location, offset: int, chunk_size: int):
    """Single raw MTProto GetFile call."""
    return await session.invoke(
        raw.functions.upload.GetFile(
            location=location,
            offset=offset,
            limit=chunk_size,
        )
    )
