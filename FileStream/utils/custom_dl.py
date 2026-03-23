"""
ByteStreamer — uses pyrogram's built-in client.get_file() for all media fetching.

client.get_file() internally handles:
  - DC routing (FileMigrate — the file is on DC1, bot is on DC5, etc.)
  - Auth export/import for foreign DCs
  - CDN file decryption
  - Reconnects and retries

offset parameter to get_file() is in units of 1 MB chunks (not bytes).
limit parameter is max number of chunks to yield.

Range-request mapping:
  from_bytes  -> offset_chunks = from_bytes // CHUNK  (skip these chunks)
              -> first_cut     = from_bytes % CHUNK   (trim start of first chunk)
  until_bytes -> last_cut      = until_bytes % CHUNK + 1 (trim end of last chunk)
  part_count  -> limit         (max chunks to fetch)
"""
import asyncio
import logging
from typing import AsyncGenerator, Dict

from pyrogram.file_id import FileId
from pyrogram.errors import (
    FileReferenceEmpty,
    FileReferenceExpired,
    FileReferenceInvalid,
)

from FileStream.config import Server
from .file_properties import get_file_ids

FILE_REF_ERRORS = (FileReferenceEmpty, FileReferenceExpired, FileReferenceInvalid)

CHUNK_SIZE = 1024 * 1024  # 1 MB — Telegram hard limit, matches get_file() internally


class ByteStreamer:
    def __init__(self, client, role: str):
        self.client = client
        self.role   = role
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

    # ── Core streaming generator ──────────────────────────────────────────

    async def yield_file(
        self,
        db_id: str,
        multi_clients: dict,
        file_id: FileId,
        offset: int,           # byte offset (from range request, aligned to chunk)
        first_part_cut: int,   # bytes to skip at start of first chunk
        last_part_cut: int,    # bytes to keep from last chunk
        part_count: int,       # total chunks to stream
        chunk_size: int,       # always CHUNK_SIZE (1 MB)
    ) -> AsyncGenerator[bytes, None]:
        retries = Server.STREAM_MAX_RETRIES
        # convert byte offset → chunk offset for get_file()
        offset_chunks = offset // CHUNK_SIZE

        while True:
            try:
                part = 0
                async for chunk in self.client.get_file(
                    file_id,
                    file_size=file_id.file_size,
                    offset=offset_chunks,
                    limit=part_count,
                ):
                    part += 1
                    if not chunk:
                        break

                    # Apply byte-level cuts on first and last chunks
                    if part_count == 1:
                        yield chunk[first_part_cut:last_part_cut]
                    elif part == 1:
                        yield chunk[first_part_cut:]
                    elif part == part_count:
                        yield chunk[:last_part_cut]
                    else:
                        yield chunk
                break  # clean exit

            except FILE_REF_ERRORS:
                if retries <= 1:
                    logging.error("[%s] File reference exhausted for %s", self.role, db_id)
                    raise
                logging.warning("[%s] File reference expired for %s — refreshing", self.role, db_id)
                file_id = await self.get_file_properties(db_id, multi_clients, force_refresh=True)
                retries -= 1

            except Exception as e:
                if retries <= 1:
                    logging.error("[%s] Stream failed for %s: %s", self.role, db_id, e)
                    raise
                logging.warning("[%s] Error for %s (%s) — retrying", self.role, db_id, e)
                retries -= 1

    async def _cache_cleaner(self) -> None:
        while True:
            await asyncio.sleep(Server.FILE_ID_CACHE_TTL)
            self._file_cache.clear()
            logging.debug("[%s] file-ID cache cleared", self.role)
