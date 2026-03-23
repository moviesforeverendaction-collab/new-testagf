import asyncio
import logging
from FileStream.bot import FileStream, multi_clients
from FileStream.utils.bot_utils import (
    is_user_banned, is_user_exist, is_user_joined,
    gen_link, is_channel_banned, is_channel_exist, is_user_authorized
)
from FileStream.utils.database import Database
from FileStream.utils.file_properties import get_file_ids, get_file_info
from FileStream.config import Telegram
from FileStream.utils.translation import EMOJI, styled_button, ButtonStyle
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup
from pyrogram.enums.parse_mode import ParseMode

db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)


@FileStream.on_message(
    filters.private
    & (
        filters.document
        | filters.video
        | filters.video_note
        | filters.audio
        | filters.voice
        | filters.animation
        | filters.photo
    ),
    group=4,
)
async def private_receive_handler(bot: Client, message: Message):
    if not await is_user_authorized(message):
        return
    if await is_user_banned(message):
        return

    await is_user_exist(bot, message)

    if Telegram.FORCE_SUB:
        if not await is_user_joined(bot, message):
            return

    try:
        inserted_id = await db.add_file(get_file_info(message))

        # Refresh file IDs — only if FLOG_CHANNEL is configured
        if Telegram.FLOG_CHANNEL:
            await get_file_ids(False, inserted_id, multi_clients, message)

        reply_markup, stream_text = await gen_link(_id=inserted_id)
        await message.reply_text(
            text=stream_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
            quote=True,
        )

    except FloodWait as e:
        await asyncio.sleep(e.value)
        if Telegram.ULOG_CHANNEL:
            try:
                await bot.send_message(
                    chat_id=Telegram.ULOG_CHANNEL,
                    text=f"FloodWait {e.value}s from [{message.from_user.first_name}](tg://user?id={message.from_user.id})",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

    except Exception as e:
        logging.error("private_receive_handler error: %s", e, exc_info=True)
        await message.reply_text(
            f"{EMOJI.err} <b>Something went wrong.</b>\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )


@FileStream.on_message(
    filters.channel
    & ~filters.forwarded
    & ~filters.media_group
    & (
        filters.document
        | filters.video
        | filters.video_note
        | filters.audio
        | filters.voice
        | filters.photo
    )
)
async def channel_receive_handler(bot: Client, message: Message):
    if await is_channel_banned(bot, message):
        return
    await is_channel_exist(bot, message)

    try:
        inserted_id = await db.add_file(get_file_info(message))

        if Telegram.FLOG_CHANNEL:
            await get_file_ids(False, inserted_id, multi_clients, message)

        reply_markup, _ = await gen_link(_id=inserted_id)
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=InlineKeyboardMarkup([[
                styled_button(
                    "Dᴏᴡɴʟᴏᴀᴅ Lɪɴᴋ",
                    url=f"https://t.me/{FileStream.username}?start=stream_{inserted_id}",
                    icon_markup=EMOJI.support,
                    style=ButtonStyle.SUCCESS,
                )
            ]])
        )

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception as e:
        logging.error("channel_receive_handler error: %s", e, exc_info=True)
        if Telegram.ULOG_CHANNEL:
            try:
                await bot.send_message(
                    chat_id=Telegram.ULOG_CHANNEL,
                    text=f"#ChannelError\n`{e}`",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
