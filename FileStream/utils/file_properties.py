from __future__ import annotations
import logging
from datetime import datetime
from pyrogram import Client
from typing import Any, Optional

from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message
from pyrogram.file_id import FileId
from FileStream.bot import FileStream
from FileStream.utils.database import Database
from FileStream.config import Telegram, Server

db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)


def _attach_file_metadata(file_id: FileId, file_info: dict) -> FileId:
    setattr(file_id, "file_size", file_info["file_size"])
    setattr(file_id, "mime_type", file_info["mime_type"])
    setattr(file_id, "file_name", file_info["file_name"])
    setattr(file_id, "unique_id", file_info["file_unique_id"])
    return file_id


def _can_use_source_file_id(client: Client, multi_clients) -> bool:
    return len(multi_clients) <= 1 or getattr(client, "id", None) == getattr(FileStream, "id", None)


async def get_file_ids(
    client: Client | bool,
    db_id: str,
    multi_clients,
    message: Message | None = None,
    force_refresh: bool = False,
) -> Optional[FileId]:
    logging.debug("Starting of get_file_ids")
    file_info = await db.get_file(db_id)
    if not client:
        if force_refresh or ("file_ids" not in file_info):
            logging.debug("Storing file_id of all clients in DB")
            refreshed_file_ids = await refresh_file_ids(db_id, file_info, multi_clients, message)
            await db.update_file_ids(db_id, refreshed_file_ids)
            logging.debug("Stored file_id of all clients in DB")
        return None

    file_id_info = file_info.get("file_ids", {})
    client_file_id = file_id_info.get(str(client.id))

    if client_file_id and not force_refresh:
        logging.debug("Using cached client-specific file_id")
        return _attach_file_metadata(FileId.decode(client_file_id), file_info)

    if not force_refresh:
        original_file_id = file_info.get("file_id")
        if original_file_id and _can_use_source_file_id(client, multi_clients):
            logging.debug("Using stored source file_id for streaming")
            return _attach_file_metadata(FileId.decode(original_file_id), file_info)

    logging.debug("Refreshing file_id for client")
    refreshed_file_ids = await refresh_file_ids(db_id, file_info, multi_clients, message)
    await db.update_file_ids(db_id, refreshed_file_ids)
    file_id_info = refreshed_file_ids

    client_file_id = file_id_info.get(str(client.id))
    if not client_file_id and _can_use_source_file_id(client, multi_clients):
        client_file_id = file_info.get("file_id")
    if not client_file_id:
        return None

    logging.debug("Middle of get_file_ids")
    file_id = _attach_file_metadata(FileId.decode(client_file_id), file_info)
    logging.debug("Ending of get_file_ids")
    return file_id


async def refresh_file_ids(db_id: str, file_info: dict, multi_clients, message: Message | None = None) -> dict:
    if Telegram.FLOG_CHANNEL is None:
        return file_info.get("file_ids", {})
    log_msg = await send_file(FileStream, db_id, file_info["file_id"], message, file_info)
    return await update_file_id(log_msg.id, multi_clients)


def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", "None")


def get_name(media_msg: Message | FileId) -> str:
    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        file_name = getattr(media, "file_name", "")

    elif isinstance(media_msg, FileId):
        file_name = getattr(media_msg, "file_name", "")

    if not file_name:
        if isinstance(media_msg, Message) and media_msg.media:
            media_type = media_msg.media.value
        elif media_msg.file_type:
            media_type = media_msg.file_type.name.lower()
        else:
            media_type = "file"

        formats = {
            "photo": "jpg", "audio": "mp3", "voice": "ogg",
            "video": "mp4", "animation": "mp4", "video_note": "mp4",
            "sticker": "webp"
        }

        ext = formats.get(media_type)
        ext = "." + ext if ext else ""

        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{media_type}-{date}{ext}"

    return file_name


def get_file_info(message):
    media = get_media_from_message(message)
    if message.chat.type == ChatType.PRIVATE:
        user_idx = message.from_user.id
    else:
        user_idx = message.chat.id
    return {
        "user_id": user_idx,
        "file_id": getattr(media, "file_id", ""),
        "file_unique_id": getattr(media, "file_unique_id", ""),
        "file_name": get_name(message),
        "file_size": getattr(media, "file_size", 0),
        "mime_type": getattr(media, "mime_type", "None/unknown")
    }


async def update_file_id(msg_id, multi_clients):
    file_ids = {}
    for client_id, client in multi_clients.items():
        log_msg = await client.get_messages(Telegram.FLOG_CHANNEL, msg_id)
        media = get_media_from_message(log_msg)
        file_ids[str(client.id)] = getattr(media, "file_id", "")

    return file_ids


async def send_file(client: Client, db_id, file_id: str, message: Message | None = None, file_info: dict | None = None):
    if isinstance(message, Message):
        file_caption = getattr(message, "caption", None) or get_name(message)
    else:
        file_caption = (file_info or {}).get("file_name") or "File"
    log_msg = await client.send_cached_media(chat_id=Telegram.FLOG_CHANNEL, file_id=file_id,
                                             caption=f'**{file_caption}**')

    if not isinstance(message, Message):
        return log_msg

    if message.chat.type == ChatType.PRIVATE:
        await log_msg.reply_text(
            text=f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ :** [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n**Uꜱᴇʀ ɪᴅ :** `{message.from_user.id}`\n**Fɪʟᴇ ɪᴅ :** `{db_id}`",
            disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN, quote=True)
    else:
        await log_msg.reply_text(
            text=f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ :** {message.chat.title} \n**Cʜᴀɴɴᴇʟ ɪᴅ :** `{message.chat.id}`\n**Fɪʟᴇ ɪᴅ :** `{db_id}`",
            disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN, quote=True)

    return log_msg
    # return await client.send_cached_media(Telegram.BIN_CHANNEL, file_id)
