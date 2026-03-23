"""
ByteStreamer — pure MTProto media downloader.

Uses client.invoke() directly — pyrogram handles all DC routing,
connection pooling, and auth internally. No manual Auth/Session
management means zero version-compatibility issues.

Prefetch pipeline: STREAM_PREFETCH concurrent GetFile calls in-flight
at all times, giving maximum throughput with no stalls between chunks.
"""
import asyncio
import contextlib
import logging
from collections import deque
from typing import AsyncGenerator, Dict

from pyrogram import raw
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.errors import (
    FileReferenceEmpty,
    FileReferenceExpired,
    FileReferenceInvalid,
)

from FileStream.config import Server
from .file_properties import get_file_ids

FILE_REF_ERRORS = (FileReferenceEmpty, FileReferenceExpired, FileReferenceInvalid)


class ByteStreamer:
    def __init__(self, client, role: str):
        self.client = client
        self.role   = role          # "dl" or "stream" — logging only
        self._file_cache: Dict[str, FileId] = {}
        asyncio.create_task(self._cache_cleaner())

    # ── File-ID cache ─────────────────────────────────────────────────────

    async def get_file_properties(
        self, db_id: str, multi_clients: dict, force_refresh: bool = False
    ) -> FileId:
        if force_refresh:
            self._file_cache.pop(db_id, None)
        if db_id not in self._file_cache:
            fid = await get_file_ids(
                self.client, db_id, multi_clients, force_refresh=force_refresh
            )
            if fid is None:
                raise RuntimeError(f"Cannot resolve file for db_id={db_id!r}")
            self._file_cache[db_id] = fid
        return self._file_cache[db_id]

    # ── File location builder ─────────────────────────────────────────────

    @staticmethod
    def _make_location(file_id: FileId):
        ft = file_id.file_type
        if ft == FileType.CHAT_PHOTO:
            from pyrogram import utils
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

    # ── Single chunk fetch via client.invoke() ────────────────────────────

    async def _fetch_chunk(self, location, offset: int, chunk_size: int) -> bytes:
        """
        Fetch one chunk using pyrogram's built-in invoke().
        Pyrogram automatically:
          - Routes to the correct DC
          - Manages the connection/session
          - Handles reconnects
        No manual Auth or Session needed.
        """
        result = await self.client.invoke(
            raw.functions.upload.GetFile(
                location=location,
                offset=offset,
                limit=chunk_size,
            )
        )
        if isinstance(result, raw.types.upload.File):
            return result.bytes
        return b""

    # ── Core streaming generator ──────────────────────────────────────────

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
            location = self._make_location(file_id)
            pending: deque[asyncio.Task] = deque()
            next_off  = cur_off
            scheduled = 0
            part      = 1

            try:
                # Pre-fill async pipeline with STREAM_PREFETCH tasks
                prefill = min(Server.STREAM_PREFETCH, remaining)
                while scheduled < prefill:
                    pending.append(asyncio.create_task(
                        self._fetch_chunk(location, next_off, chunk_size)
                    ))
                    next_off  += chunk_size
                    scheduled += 1

                # Drain pipeline, keep it full
                while part <= remaining and pending:
                    chunk = await pending.popleft()

                    # Schedule next chunk immediately to keep pipeline full
                    if scheduled < remaining:
                        pending.append(asyncio.create_task(
                            self._fetch_chunk(location, next_off, chunk_size)
                        ))
                        next_off  += chunk_size
                        scheduled += 1

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

                break  # clean exit

            except FILE_REF_ERRORS:
                if retries <= 1:
                    logging.error("[%s] File reference refresh exhausted for %s", self.role, db_id)
                    raise
                logging.warning("[%s] File reference expired for %s — refreshing", self.role, db_id)
                file_id   = await self.get_file_properties(db_id, multi_clients, force_refresh=True)
                cur_off  += (part - 1) * chunk_size
                remaining -= part - 1
                cur_cut    = 0 if yielded else cur_cut
                retries   -= 1

            except (TimeoutError, OSError, ConnectionError, AttributeError):
                if retries <= 1:
                    logging.error("[%s] Stream failed after all retries for %s", self.role, db_id)
                    raise
                logging.warning("[%s] Transient error for %s — retrying", self.role, db_id)
                cur_off  += (part - 1) * chunk_size
                remaining -= part - 1
                cur_cut    = 0 if yielded else cur_cut
                retries   -= 1

            finally:
                # Cancel any still-pending prefetch tasks
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
