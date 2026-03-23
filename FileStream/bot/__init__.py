from ..config import Telegram
from pyrogram import Client

if Telegram.SECONDARY:
    plugins   = None
    no_updates = True
else:
    plugins   = {"root": "FileStream/bot/plugins"}
    no_updates = None

# ── The one bot — commands only ───────────────────────────────────────────
FileStream = Client(
    name="FileStream",
    api_id=Telegram.API_ID,
    api_hash=Telegram.API_HASH,
    workdir="FileStream",
    plugins=plugins,
    bot_token=Telegram.BOT_TOKEN,
    sleep_threshold=Telegram.SLEEP_THRESHOLD,
    workers=Telegram.WORKERS,
    no_updates=no_updates,
)

# ── Two raw MTProto clients (populated by clients.py at startup) ──────────
# dl_client  → Account 1 (API_ID  / API_HASH)   — serves /dl
# str_client → Account 2 (API_ID_2 / API_HASH_2) — serves /watch
dl_client  = None   # type: Client | None
str_client = None   # type: Client | None

# work_load counters
work_loads = {"dl": 0, "stream": 0}

# used by file_properties for file-id resolution
multi_clients = {}
