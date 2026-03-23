import logging
import math
from FileStream import __version__
from FileStream.bot import FileStream
from FileStream.exceptions import FIleNotFound
from FileStream.utils.bot_utils import gen_linkx, verify_user
from FileStream.config import Telegram
from FileStream.utils.database import Database
from FileStream.utils.translation import LANG, BUTTON, EMOJI, MEDIA, styled_button, ButtonStyle
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums.parse_mode import ParseMode
import asyncio

db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)


def get_start_media() -> str:
    return Telegram.START_PIC or MEDIA.PROJECTS_PHOTO


def get_help_media() -> str:
    return Telegram.START_PIC or MEDIA.HELP_PHOTO_URL

@FileStream.on_message(filters.command('start') & filters.private)
async def start(bot: Client, message: Message):
    if not await verify_user(bot, message):
        return
    usr_cmd = message.text.split("_")[-1]

    if usr_cmd == "/start":
        await message.reply_photo(
            photo=get_start_media(),
            caption=LANG.START_TEXT.format(message.from_user.mention, FileStream.username),
            parse_mode=ParseMode.HTML,
            reply_markup=BUTTON.START_BUTTONS
        )
    else:
        if "stream_" in message.text:
            try:
                file_check = await db.get_file(usr_cmd)
                file_id = str(file_check['_id'])
                if file_id == usr_cmd:
                    reply_markup, stream_text = await gen_linkx(m=message, _id=file_id,
                                                                name=[FileStream.username, FileStream.fname])
                    await message.reply_text(
                        text=stream_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=reply_markup,
                        quote=True
                    )

            except FIleNotFound as e:
                await message.reply_text(LANG.FILE_NOT_FOUND_TEXT, parse_mode=ParseMode.HTML)
            except Exception as e:
                await message.reply_text(LANG.SOMETHING_WENT_WRONG, parse_mode=ParseMode.HTML)
                logging.error(e)

        elif "file_" in message.text:
            try:
                file_check = await db.get_file(usr_cmd)
                db_id = str(file_check['_id'])
                file_id = file_check['file_id']
                file_name = file_check['file_name']
                if db_id == usr_cmd:
                    filex = await message.reply_cached_media(file_id=file_id, caption=f'**{file_name}**')
                    await asyncio.sleep(3600)
                    try:
                        await filex.delete()
                        await message.delete()
                    except Exception:
                        pass

            except FIleNotFound as e:
                await message.reply_text(LANG.FILE_NOT_FOUND_TEXT, parse_mode=ParseMode.HTML)
            except Exception as e:
                await message.reply_text(LANG.SOMETHING_WENT_WRONG, parse_mode=ParseMode.HTML)
                logging.error(e)

        else:
            await message.reply_text(f"{EMOJI.invalid} <b>Invalid command.</b>", parse_mode=ParseMode.HTML)

@FileStream.on_message(filters.private & filters.command(["about"]))
async def about_handler(bot, message):
    if not await verify_user(bot, message):
        return
    await message.reply_photo(
        photo=get_start_media(),
        caption=LANG.ABOUT_TEXT.format(FileStream.fname, __version__),
        parse_mode=ParseMode.HTML,
        reply_markup=BUTTON.ABOUT_BUTTONS
    )

@FileStream.on_message((filters.command('help')) & filters.private)
async def help_handler(bot, message):
    if not await verify_user(bot, message):
        return
    await message.reply_photo(
        photo=get_help_media(),
        caption=LANG.HELP_TEXT.format(Telegram.OWNER_ID),
        parse_mode=ParseMode.HTML,
        reply_markup=BUTTON.HELP_BUTTONS
    )

# ---------------------------------------------------------------------------------------------------

@FileStream.on_message(filters.command('files') & filters.private)
async def my_files(bot: Client, message: Message):
    if not await verify_user(bot, message):
        return
    user_files, total_files = await db.find_files(message.from_user.id, [1, 10])

    file_list = []
    async for x in user_files:
        file_list.append([
            styled_button(
                x["file_name"],
                callback_data=f"myfile_{x['_id']}_{1}",
                icon_markup=EMOJI.view,
                style=ButtonStyle.PRIMARY,
            )
        ])
    if total_files > 10:
        file_list.append(
            [
                styled_button("◄", callback_data="N/A", icon_markup=EMOJI.round, style=ButtonStyle.PRIMARY),
                styled_button(f"1/{math.ceil(total_files / 10)}", callback_data="N/A", icon_markup=EMOJI.status, style=ButtonStyle.PRIMARY),
                styled_button("►", callback_data="userfiles_2", icon_markup=EMOJI.round, style=ButtonStyle.PRIMARY)
            ],
        )
    if not file_list:
        file_list.append(
            [styled_button("Eᴍᴘᴛʏ", callback_data="N/A", icon_markup=EMOJI.empty, style=ButtonStyle.PRIMARY)],
        )
    file_list.append([styled_button("Cʟᴏsᴇ", callback_data="close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER)])
    await message.reply_photo(photo=Telegram.FILE_PIC,
                              caption=f"{EMOJI.stats} <b>Total files:</b> <code>{total_files}</code>",
                              parse_mode=ParseMode.HTML,
                              reply_markup=InlineKeyboardMarkup(file_list))
