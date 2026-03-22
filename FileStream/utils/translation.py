import inspect
import re
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from FileStream.config import Telegram

try:
    from pyrogram.enums import ButtonStyle as _PyrogramButtonStyle
except ImportError:
    _PyrogramButtonStyle = None


class ButtonStyle:
    DEFAULT = getattr(_PyrogramButtonStyle, "DEFAULT", None)
    PRIMARY = getattr(_PyrogramButtonStyle, "PRIMARY", None)
    DANGER = getattr(_PyrogramButtonStyle, "DANGER", None)
    SUCCESS = getattr(_PyrogramButtonStyle, "SUCCESS", None)


INLINE_BUTTON_PARAMS = inspect.signature(InlineKeyboardButton.__init__).parameters
SUPPORTS_BUTTON_STYLE = "style" in INLINE_BUTTON_PARAMS and _PyrogramButtonStyle is not None
SUPPORTS_ICON_CUSTOM_EMOJI = "icon_custom_emoji_id" in INLINE_BUTTON_PARAMS


def tg_emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def emoji_id(markup: str) -> int | None:
    match = re.search(r'emoji-id="(\d+)"', markup)
    return int(match.group(1)) if match else None


def styled_button(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    icon_markup: str | None = None,
    icon_custom_emoji_id: int | None = None,
    style: ButtonStyle = ButtonStyle.DEFAULT,
) -> InlineKeyboardButton:
    icon_id = icon_custom_emoji_id or (emoji_id(icon_markup) if icon_markup else None)
    kwargs = dict(
        text=text,
        callback_data=callback_data,
        url=url,
    )
    if SUPPORTS_ICON_CUSTOM_EMOJI and icon_id is not None:
        kwargs["icon_custom_emoji_id"] = icon_id
    if SUPPORTS_BUTTON_STYLE and style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(
        **kwargs,
    )


class EMOJI:
    premium = tg_emoji("5886572637051687349", "⭐️")
    free = tg_emoji("5284976439051954090", "🆓")
    cancel = tg_emoji("5019523782004441717", "❌")
    verified = tg_emoji("6003524390363338167", "✅")
    delete = tg_emoji("6089405688830760608", "🗑")
    banned = tg_emoji("5208778775713554782", "🤡")
    r = tg_emoji("6122699051243671018", "🥲")
    maintenance = tg_emoji("5440621591387980068", "🔜")
    check = tg_emoji("6122648774356504384", "✅")
    verified_2 = tg_emoji("6057871613741766194", "✅")
    stats = tg_emoji("6068794518734378500", "📊")
    limit = tg_emoji("6087079603262724786", "🚫")
    rate = tg_emoji("5796283422238314412", "💎")
    welcome = tg_emoji("5206308490913531300", "😊")
    hello = tg_emoji("5226645496067542621", "🙋‍♀️")
    quick = tg_emoji("5440584710503825074", "🈳")
    cmd = tg_emoji("5471978009449731768", "👉")
    req = tg_emoji("5192853114289425458", "🐈")
    dev = tg_emoji("6057354851866645157", "😈")
    support = tg_emoji("5796664978542956370", "⬇️")
    updates = tg_emoji("5796664978542956370", "⬇️")
    upload = tg_emoji("6095722176973904112", "😈")
    zip = tg_emoji("6122735807573789902", "💀")
    send = tg_emoji("5391072026867802122", "😎")
    large = tg_emoji("5222463202943575830", "🦣")
    load = tg_emoji("5258400839281681797", "📝")
    security = tg_emoji("5251203410396458957", "🛡")
    missing = tg_emoji("5192926837403061706", "😏")
    err = tg_emoji("5260342697075416641", "❌")
    detected = tg_emoji("5855178350263276469", "⚠️")
    not_allowed = tg_emoji("5855178350263276469", "⚠️")
    enter = tg_emoji("5192835032477112483", "🎶")
    invalid = tg_emoji("5855178350263276469", "⚠️")
    not_accepted = tg_emoji("5260342697075416641", "❌")
    deploying = tg_emoji("5192736428617931088", "🏩")
    success = tg_emoji("5416044289576673808", "🔴")
    alert = tg_emoji("5855178350263276469", "⚠️")
    round = tg_emoji("5818711397860642669", "⏺")
    failed = tg_emoji("5855178350263276469", "⚠️")
    i = tg_emoji("5334544901428229844", "ℹ️")
    clone = tg_emoji("6120564207684424205", "😜")
    empty = tg_emoji("5206685498847806032", "🌟")
    project_em = tg_emoji("5429651785352501917", "↗️")
    validate = tg_emoji("5336985409220001678", "✅")
    help = tg_emoji("5449728678697124453", "🆘")
    benifits = tg_emoji("5193177581888755275", "💻")
    thanks = tg_emoji("5206285830666076912", "🌟")
    view = tg_emoji("6120706182123360381", "😀")
    stop = tg_emoji("5440472697756744614", "✋")
    contact = tg_emoji("6055505391704348123", "🤩")
    issue = tg_emoji("5841463476010093659", "🤖")
    logs = tg_emoji("5325625353866070316", "3️⃣")
    build = tg_emoji("5197371802136892976", "⛏")
    select = tg_emoji("5192873528268984106", "😊")
    not_found = tg_emoji("5242232799968107180", "🤷‍♂️")
    date = tg_emoji("5287606810168028257", "🗓")
    usage = tg_emoji("5238195277306808352", "🐱")
    deleted = tg_emoji("5258130763148172425", "🗑")
    stoped = tg_emoji("5440472697756744614", "✋")
    restarted = tg_emoji("5017470156276761427", "🔄")
    refreshed = tg_emoji("5231204977514399349", "👍")
    oversmart = tg_emoji("5384189479214943737", "🤩")
    warn = tg_emoji("5447644880824181073", "⚠️")
    wipe_alert = tg_emoji("5447644880824181073", "⚠️")
    unknown = tg_emoji("5327917526372328990", "❓")
    timeout = tg_emoji("5458640241915084025", "⏱")
    status = tg_emoji("6068794518734378500", "📊")
    github = tg_emoji("5323375426658124630", "4️⃣")


class ICONS:
    PANEL = 5258301131615912800


class MEDIA:
    START_VIDEO = "BAACAgUAAxkBAAMDaZQUDzsZvpWwlkSdj93dJJD6Df4AAt8bAAJceKFUeS-RMLP1W4Q6BA"
    UPLOAD_VIDEO = "BAACAgUAAxkBAAMLaZQjr43zV6rZM_AF6rG527IvcU4AAh0YAAI1z6FUWU8BzwE_O-06BA"
    PREMIUM_VIDEO = "BAACAgUAAxkBAAMNaZQjy6vOFo-y6BEz2JhOmSqvNOUAAh4YAAI1z6FU2bnGR2Qh6VQ6BA"
    HELP_VIDEO = "BAACAgUAAxkBAAMJaZQjg7WcdU2QC4P_aA5YCwJaMz4AAhwYAAI1z6FUnCt-RLVzS6M6BA"
    PROJECTS_PHOTO = "https://graph.org/file/ffd8ad6427587f056a820-1633d78adbc7d8984f.jpg"
    HELP_PHOTO_URL = "https://graph.org/file/e92a6d61c7bbd924bc8df-b491d1e337de4ba603.jpg"
    SUPPORT_URL = "https://t.me/TEAM_X_OG"


class LANG(object):
    START_TEXT = f"""
{EMOJI.hello} <b>Hey, {{}}</b>

{EMOJI.welcome} <b>I'm a Telegram file streaming bot and direct link generator.</b>
{EMOJI.verified} <b>I work in private chats and channels.</b>
{EMOJI.updates} <b>Updates:</b> <code>@{{}}</code>
"""

    HELP_TEXT = f"""
{EMOJI.help} <b>How to use me</b>

{EMOJI.cmd} <b>Add me as admin in your channel.</b>
{EMOJI.send} <b>Send me any media or document.</b>
{EMOJI.view} <b>I will generate stream and direct download links.</b>
{EMOJI.alert} <b>Adult content is strictly prohibited.</b>
{EMOJI.contact} <b>Need help?</b> <a href='https://t.me/TEAM_X_OG'>Support Chat</a>
{EMOJI.dev} <b>Developer:</b> <a href='tg://user?id={{}}'>tap here</a>
"""

    ABOUT_TEXT = f"""
{EMOJI.i} <b>Bot Name:</b> {{}}
{EMOJI.build} <b>Version:</b> <code>{{}}</code>
{EMOJI.date} <b>Updated On:</b> <code>22-March-2026</code>
{EMOJI.dev} <b>Developer:</b> <a href='https://telegram.me/AvishkarPatil'>Avishkar Patil</a>
{EMOJI.project_em} <b>Support:</b> <a href='https://t.me/TEAM_X_OG'>TEAM_X_OG</a>
"""

    STREAM_TEXT = f"""
{EMOJI.verified_2} <b>Your links are ready</b>

{EMOJI.req} <b>File Name:</b> <code>{{}}</code>
{EMOJI.large} <b>File Size:</b> <code>{{}}</code>
{EMOJI.support} <b>Download:</b> <code>{{}}</code>
{EMOJI.view} <b>Watch:</b> <code>{{}}</code>
{EMOJI.send} <b>Get File:</b> <code>{{}}</code>
"""

    STREAM_TEXT_X = f"""
{EMOJI.verified_2} <b>Your links are ready</b>

{EMOJI.req} <b>File Name:</b> <code>{{}}</code>
{EMOJI.large} <b>File Size:</b> <code>{{}}</code>
{EMOJI.support} <b>Download:</b> <code>{{}}</code>
{EMOJI.send} <b>Get File:</b> <code>{{}}</code>
"""

    BAN_TEXT = f"{EMOJI.banned} <b>Sorry, you are banned from using this bot.</b>\n\n{EMOJI.contact} <b><a href='tg://user?id={{}}'>Contact Developer</a></b>"

    FORCE_SUB_TEXT = f"{EMOJI.security} <i>Join my updates channel to use me.</i>"
    FORCE_SUB_FAIL_TEXT = f"{EMOJI.err} <i>Something went wrong. Contact support from the updates channel.</i> <b><a href='https://t.me/{Telegram.UPDATES_CHANNEL}'>[ click here ]</a></b>"
    UNAUTHORIZED_TEXT = f"{EMOJI.not_allowed} <b>You are not authorized to use this bot.</b>"
    FILE_NOT_FOUND_TEXT = f"{EMOJI.not_found} <b>File not found.</b>"
    SOMETHING_WENT_WRONG = f"{EMOJI.err} <b>Something went wrong.</b>"


class BUTTON(object):
    START_BUTTONS = InlineKeyboardMarkup(
        [
            [
                styled_button("H𝙴𝙻𝙿", callback_data="help", icon_custom_emoji_id=ICONS.PANEL, style=ButtonStyle.PRIMARY),
                styled_button("Sᴜᴘᴘᴏʀᴛ", url=MEDIA.SUPPORT_URL, icon_custom_emoji_id=ICONS.PANEL, style=ButtonStyle.PRIMARY),
            ],
            [
                styled_button("Uᴘᴅᴀᴛᴇs", url=f'https://t.me/{Telegram.UPDATES_CHANNEL}', icon_markup=EMOJI.updates, style=ButtonStyle.SUCCESS),
                styled_button("Aʙᴏᴜᴛ", callback_data="about", icon_markup=EMOJI.i, style=ButtonStyle.DEFAULT),
            ],
            [
                styled_button("Cʟᴏsᴇ", callback_data="close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER),
            ],
        ]
    )

    HELP_BUTTONS = InlineKeyboardMarkup(
        [
            [
                styled_button("Hᴏᴍᴇ", callback_data="home", icon_markup=EMOJI.welcome, style=ButtonStyle.PRIMARY),
                styled_button("Aʙᴏᴜᴛ", callback_data="about", icon_markup=EMOJI.i, style=ButtonStyle.DEFAULT),
            ],
            [
                styled_button("Sᴜᴘᴘᴏʀᴛ", url=MEDIA.SUPPORT_URL, icon_custom_emoji_id=ICONS.PANEL, style=ButtonStyle.PRIMARY),
                styled_button("Cʟᴏsᴇ", callback_data="close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER),
            ],
        ]
    )

    ABOUT_BUTTONS = InlineKeyboardMarkup(
        [
            [
                styled_button("Hᴏᴍᴇ", callback_data="home", icon_markup=EMOJI.welcome, style=ButtonStyle.PRIMARY),
                styled_button("H𝙴𝙻𝙿", callback_data="help", icon_custom_emoji_id=ICONS.PANEL, style=ButtonStyle.PRIMARY),
            ],
            [
                styled_button("Sᴜᴘᴘᴏʀᴛ", url=MEDIA.SUPPORT_URL, icon_custom_emoji_id=ICONS.PANEL, style=ButtonStyle.PRIMARY),
                styled_button("Cʟᴏsᴇ", callback_data="close", icon_markup=EMOJI.cancel, style=ButtonStyle.DANGER),
            ],
        ]
    )
