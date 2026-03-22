import datetime
import math
from FileStream import __version__
from FileStream.bot import FileStream
from FileStream.config import Telegram, Server
from FileStream.utils.translation import LANG, BUTTON, EMOJI, styled_button
from FileStream.utils.bot_utils import gen_link
from FileStream.utils.database import Database
from FileStream.utils.human_readable import humanbytes
from FileStream.server.exceptions import FIleNotFound
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.file_id import FileId, FileType, PHOTO_TYPES
from pyrogram.enums.parse_mode import ParseMode
db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)


async def edit_panel_message(update: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    if update.message.media:
        await update.message.edit_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    else:
        await update.message.edit_text(
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )

#---------------------[ START CMD ]---------------------#
@FileStream.on_callback_query()
async def cb_data(bot, update: CallbackQuery):
    usr_cmd = update.data.split("_")
    if usr_cmd[0] == "home":
        await edit_panel_message(
            update,
            text=LANG.START_TEXT.format(update.from_user.mention, FileStream.username),
            reply_markup=BUTTON.START_BUTTONS
        )
    elif usr_cmd[0] == "help":
        await edit_panel_message(
            update,
            text=LANG.HELP_TEXT.format(Telegram.OWNER_ID),
            reply_markup=BUTTON.HELP_BUTTONS
        )
    elif usr_cmd[0] == "about":
        await edit_panel_message(
            update,
            text=LANG.ABOUT_TEXT.format(FileStream.fname, __version__),
            reply_markup=BUTTON.ABOUT_BUTTONS
        )

    #---------------------[ MY FILES CMD ]---------------------#

    elif usr_cmd[0] == "N/A":
        await update.answer("N/A", True)
    elif usr_cmd[0] == "close":
        await update.message.delete()
    elif usr_cmd[0] == "msgdelete":
        await update.message.edit_caption(
        caption=f"{EMOJI.warn} <b>Confirm you want to delete this file.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            styled_button("Yᴇs", callback_data=f"msgdelyes_{usr_cmd[1]}_{usr_cmd[2]}", icon_markup=EMOJI.delete, style=ButtonStyle.DANGER),
            styled_button("Nᴏ", callback_data=f"myfile_{usr_cmd[1]}_{usr_cmd[2]}", icon_markup=EMOJI.cancel, style=ButtonStyle.DEFAULT)]])
    )
    elif usr_cmd[0] == "msgdelyes":
        await delete_user_file(usr_cmd[1], int(usr_cmd[2]), update)
        return
    elif usr_cmd[0] == "msgdelpvt":
        await update.message.edit_caption(
        caption=f"{EMOJI.warn} <b>Confirm you want to delete this file.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            styled_button("Yᴇs", callback_data=f"msgdelpvtyes_{usr_cmd[1]}", icon_markup=EMOJI.delete, style=ButtonStyle.DANGER),
            styled_button("Nᴏ", callback_data=f"mainstream_{usr_cmd[1]}", icon_markup=EMOJI.cancel, style=ButtonStyle.DEFAULT)]])
    )
    elif usr_cmd[0] == "msgdelpvtyes":
        await delete_user_filex(usr_cmd[1], update)
        return

    elif usr_cmd[0] == "mainstream":
        _id = usr_cmd[1]
        reply_markup, stream_text = await gen_link(_id=_id)
        await update.message.edit_text(
            text=stream_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )

    elif usr_cmd[0] == "userfiles":
        file_list, total_files = await gen_file_list_button(int(usr_cmd[1]), update.from_user.id)
        await update.message.edit_caption(
            caption=f"{EMOJI.stats} <b>Total files:</b> <code>{total_files}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(file_list)
            )
    elif usr_cmd[0] == "myfile":
        await gen_file_menu(usr_cmd[1], usr_cmd[2], update)
        return
    elif usr_cmd[0] == "sendfile":
        myfile = await db.get_file(usr_cmd[1])
        file_name = myfile['file_name']
        await update.answer(f"Sending File {file_name}")
        await update.message.reply_cached_media(myfile['file_id'], caption=f'**{file_name}**')
    else:
        await update.message.delete()



    #---------------------[ MY FILES FUNC ]---------------------#

async def gen_file_list_button(file_list_no: int, user_id: int):

    file_range=[file_list_no*10-10+1, file_list_no*10]
    user_files, total_files=await db.find_files(user_id, file_range)

    file_list=[]
    async for x in user_files:
        file_list.append([
            styled_button(
                x["file_name"],
                callback_data=f"myfile_{x['_id']}_{file_list_no}",
                icon_markup=EMOJI.view,
                style=ButtonStyle.DEFAULT,
            )
        ])
    if total_files > 10:
        file_list.append(
                [
                    styled_button("◄", callback_data="{}".format("userfiles_"+str(file_list_no-1) if file_list_no > 1 else 'N/A'), icon_markup=EMOJI.round, style=ButtonStyle.DEFAULT),
                    styled_button(f"{file_list_no}/{math.ceil(total_files/10)}", callback_data="N/A", icon_markup=EMOJI.status, style=ButtonStyle.DEFAULT),
                    styled_button("►", callback_data="{}".format("userfiles_"+str(file_list_no+1) if total_files > file_list_no*10 else 'N/A'), icon_markup=EMOJI.round, style=ButtonStyle.DEFAULT),
                ]
        )
    if not file_list:
        file_list.append(
                [styled_button("Eᴍᴘᴛʏ", callback_data="N/A", icon_markup=EMOJI.empty, style=ButtonStyle.DEFAULT)])
    file_list.append([styled_button("Cʟᴏsᴇ", callback_data="close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER)])
    return file_list, total_files

async def gen_file_menu(_id, file_list_no, update: CallbackQuery):
    try:
        myfile_info=await db.get_file(_id)
    except FIleNotFound:
        await update.answer("File Not Found")
        return

    file_id=FileId.decode(myfile_info['file_id'])

    if file_id.file_type in PHOTO_TYPES:
        file_type = "Image"
    elif file_id.file_type == FileType.VOICE:
        file_type = "Voice"
    elif file_id.file_type in (FileType.VIDEO, FileType.ANIMATION, FileType.VIDEO_NOTE):
        file_type = "Video"
    elif file_id.file_type == FileType.DOCUMENT:
        file_type = "Document"
    elif file_id.file_type == FileType.STICKER:
        file_type = "Sticker"
    elif file_id.file_type == FileType.AUDIO:
        file_type = "Audio"
    else:
        file_type = "Unknown"

    page_link = f"{Server.URL}watch/{myfile_info['_id']}"
    stream_link = f"{Server.URL}dl/{myfile_info['_id']}"
    if "video" in file_type.lower():
        MYFILES_BUTTONS = InlineKeyboardMarkup(
            [
                [
                    styled_button("Sᴛʀᴇᴀᴍ", url=page_link, icon_markup=EMOJI.view, style=ButtonStyle.PRIMARY),
                    styled_button("Dᴏᴡɴʟᴏᴀᴅ", url=stream_link, icon_markup=EMOJI.support, style=ButtonStyle.SUCCESS),
                ],
                [
                    styled_button("Gᴇᴛ Fɪʟᴇ", callback_data=f"sendfile_{myfile_info['_id']}", icon_markup=EMOJI.send, style=ButtonStyle.DEFAULT),
                    styled_button("Rᴇᴠᴏᴋᴇ", callback_data=f"msgdelete_{myfile_info['_id']}_{file_list_no}", icon_markup=EMOJI.delete, style=ButtonStyle.DANGER),
                ],
                [styled_button("Bᴀᴄᴋ", callback_data="userfiles_{}".format(file_list_no), icon_markup=EMOJI.round, style=ButtonStyle.DEFAULT)]
            ]
        )
    else:
        MYFILES_BUTTONS = InlineKeyboardMarkup(
            [
                [styled_button("Dᴏᴡɴʟᴏᴀᴅ", url=stream_link, icon_markup=EMOJI.support, style=ButtonStyle.SUCCESS)],
                [
                    styled_button("Gᴇᴛ Fɪʟᴇ", callback_data=f"sendfile_{myfile_info['_id']}", icon_markup=EMOJI.send, style=ButtonStyle.DEFAULT),
                    styled_button("Rᴇᴠᴏᴋᴇ", callback_data=f"msgdelete_{myfile_info['_id']}_{file_list_no}", icon_markup=EMOJI.delete, style=ButtonStyle.DANGER),
                ],
                [styled_button("Bᴀᴄᴋ", callback_data="userfiles_{}".format(file_list_no), icon_markup=EMOJI.round, style=ButtonStyle.DEFAULT)]
            ]
        )

    TiMe = myfile_info['time']
    if type(TiMe) == float:
        date = datetime.datetime.fromtimestamp(TiMe)
    await update.edit_message_caption(
        caption="{}\n{}\n{}\n{}".format(
            f"{EMOJI.req} <b>File Name:</b> <code>{myfile_info['file_name']}</code>",
            f"{EMOJI.large} <b>File Size:</b> <code>{humanbytes(int(myfile_info['file_size']))}</code>",
            f"{EMOJI.i} <b>File Type:</b> <code>{file_type}</code>",
            f"{EMOJI.date} <b>Created On:</b> <code>{TiMe if isinstance(TiMe, str) else date.date()}</code>",
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=MYFILES_BUTTONS )


async def delete_user_file(_id, file_list_no: int, update:CallbackQuery):

    try:
        myfile_info=await db.get_file(_id)
    except FIleNotFound:
        await update.answer("File Already Deleted")
        return

    await db.delete_one_file(myfile_info['_id'])
    await db.count_links(update.from_user.id, "-")
    await update.message.edit_caption(
            caption=f"{EMOJI.deleted} <b>File deleted successfully.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[styled_button("Bᴀᴄᴋ", callback_data=f"userfiles_1", icon_markup=EMOJI.round, style=ButtonStyle.DEFAULT)]])
        )

async def delete_user_filex(_id, update:CallbackQuery):

    try:
        myfile_info=await db.get_file(_id)
    except FIleNotFound:
        await update.answer("File Already Deleted")
        return

    await db.delete_one_file(myfile_info['_id'])
    await db.count_links(update.from_user.id, "-")
    await update.message.edit_caption(
            caption=f"{EMOJI.deleted} <b>File deleted successfully.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[styled_button("Cʟᴏsᴇ", callback_data=f"close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER)]])
        )
