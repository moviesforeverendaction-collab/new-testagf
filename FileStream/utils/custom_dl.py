import asyncio
import contextlib
import logging
from collections import deque
from typing import Dict, Union
from FileStream.bot import work_loads
from FileStream.config import Server
from pyrogram import Client, utils, raw
from .file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.types import Message

class ByteStreamer:
    def __init__(self, client: Client):
        self.clean_timer = Server.FILE_ID_CACHE_TTL
        self.client: Client = client
        self.cached_file_ids: Dict[str, FileId] = {}
        self.media_session_pools: dict[int, list[Session]] = {}
        self.media_session_locks: dict[int, asyncio.Lock] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, db_id: str, multi_clients) -> FileId:
        """
        Returns the properties of a media of a specific message in a FIleId class.
        if the properties are cached, then it'll return the cached results.
        or it'll generate the properties from the Message ID and cache them.
        """
        if not db_id in self.cached_file_ids:
            logging.debug("Before Calling generate_file_properties")
            await self.generate_file_properties(db_id, multi_clients)
            logging.debug(f"Cached file properties for file with ID {db_id}")
        return self.cached_file_ids[db_id]
    
    async def generate_file_properties(self, db_id: str, multi_clients) -> FileId:
        """
        Generates the properties of a media file on a specific message.
        returns ths properties in a FIleId class.
        """
        logging.debug("Before calling get_file_ids")
        file_id = await get_file_ids(self.client, db_id, multi_clients, Message)
        logging.debug(f"Generated file ID and Unique ID for file with ID {db_id}")
        self.cached_file_ids[db_id] = file_id
        logging.debug(f"Cached media file with ID {db_id}")
        return self.cached_file_ids[db_id]

    def _get_media_session_lock(self, dc_id: int) -> asyncio.Lock:
        if dc_id not in self.media_session_locks:
            self.media_session_locks[dc_id] = asyncio.Lock()
        return self.media_session_locks[dc_id]

    async def _create_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Generates a media session for the DC that contains the media file.
        This is required for getting the bytes from Telegram servers.
        """
        if file_id.dc_id != await client.storage.dc_id():
            media_session = Session(
                client,
                file_id.dc_id,
                await Auth(
                    client, file_id.dc_id, await client.storage.test_mode()
                ).create(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()

            for _ in range(6):
                exported_auth = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=file_id.dc_id)
                )

                try:
                    await media_session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported_auth.id, bytes=exported_auth.bytes
                        )
                    )
                    break
                except AuthBytesInvalid:
                    logging.debug(
                        f"Invalid authorization bytes for DC {file_id.dc_id}"
                    )
                    continue
            else:
                await media_session.stop()
                raise AuthBytesInvalid
        else:
            media_session = Session(
                client,
                file_id.dc_id,
                await client.storage.auth_key(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()
        logging.debug(f"Created media session for DC {file_id.dc_id}")
        return media_session

    async def generate_media_sessions(self, client: Client, file_id: FileId) -> list[Session]:
        """
        Creates and caches a pool of media sessions for the target DC so a single
        bot can keep multiple Telegram file requests in flight at once.
        """
        dc_id = file_id.dc_id
        media_sessions = self.media_session_pools.get(dc_id)

        if media_sessions:
            logging.debug(f"Using cached media session pool for DC {dc_id}")
            return media_sessions

        async with self._get_media_session_lock(dc_id):
            media_sessions = self.media_session_pools.get(dc_id)
            if media_sessions:
                logging.debug(f"Using cached media session pool for DC {dc_id}")
                return media_sessions

            media_sessions = []
            cached_session = client.media_sessions.get(dc_id)

            if cached_session is None:
                cached_session = await self._create_media_session(client, file_id)
                client.media_sessions[dc_id] = cached_session

            media_sessions.append(cached_session)

            while len(media_sessions) < Server.MEDIA_SESSION_POOL_SIZE:
                media_sessions.append(await self._create_media_session(client, file_id))

            self.media_session_pools[dc_id] = media_sessions
            logging.debug(
                f"Created media session pool with {len(media_sessions)} sessions for DC {dc_id}"
            )
            return media_sessions

    @staticmethod
    async def get_location(file_id: FileId) -> Union[raw.types.InputPhotoFileLocation,
                                                     raw.types.InputDocumentFileLocation,
                                                     raw.types.InputPeerPhotoFileLocation,]:
        """
        Returns the file location for the media file.
        """
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )

            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return location

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ) -> Union[str, None]:
        """
        Custom generator that yields the bytes of the media file.
        Modded from <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py#L20>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        client = self.client
        work_loads[index] += 1
        logging.debug(f"Starting to yielding file with client {index}.")
        media_sessions = await self.generate_media_sessions(client, file_id)

        current_part = 1
        location = await self.get_location(file_id)
        pending_chunks = deque()
        next_offset = offset
        scheduled_parts = 0
        session_count = len(media_sessions)

        try:
            while scheduled_parts < min(Server.STREAM_PREFETCH, part_count):
                pending_chunks.append(
                    asyncio.create_task(
                        self._get_file_chunk(
                            media_sessions[scheduled_parts % session_count],
                            location,
                            next_offset,
                            chunk_size,
                        )
                    )
                )
                next_offset += chunk_size
                scheduled_parts += 1

            while current_part <= part_count and pending_chunks:
                response = await pending_chunks.popleft()

                if scheduled_parts < part_count:
                    pending_chunks.append(
                        asyncio.create_task(
                            self._get_file_chunk(
                                media_sessions[scheduled_parts % session_count],
                                location,
                                next_offset,
                                chunk_size,
                            )
                        )
                    )
                    next_offset += chunk_size
                    scheduled_parts += 1

                if not isinstance(response, raw.types.upload.File):
                    break

                chunk = response.bytes
                if not chunk:
                    break

                if part_count == 1:
                    yield chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                current_part += 1
        except (TimeoutError, AttributeError):
            pass
        finally:
            while pending_chunks:
                pending_chunk = pending_chunks.popleft()
                if not pending_chunk.done():
                    pending_chunk.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pending_chunk
            logging.debug(f"Finished yielding file with {current_part} parts.")
            work_loads[index] -= 1

    @staticmethod
    async def _get_file_chunk(
        media_session: Session,
        location: Union[
            raw.types.InputPhotoFileLocation,
            raw.types.InputDocumentFileLocation,
            raw.types.InputPeerPhotoFileLocation,
        ],
        offset: int,
        chunk_size: int,
    ):
        return await media_session.invoke(
            raw.functions.upload.GetFile(
                location=location,
                offset=offset,
                limit=chunk_size,
            ),
        )

    
    async def clean_cache(self) -> None:
        """
        function to clean the cache to reduce memory usage
        """
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logging.debug("Cleaned the cache")
