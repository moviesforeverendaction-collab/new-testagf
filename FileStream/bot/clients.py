"""
Starts two bare MTProto clients — no bot token, no session string.
Pyrogram connects using only API_ID + API_HASH and stores its own
auth data inside the client's in-memory storage.

Account 1 (API_ID / API_HASH)    → dl_client  → /dl  (downloads)
Account 2 (API_ID_2 / API_HASH_2) → str_client → /watch (streaming)

Both clients use `no_updates=True` so they never consume the update
queue — they are pure MTProto data channels.
"""
import logging
import FileStream.bot as _bot
from pyrogram import Client
from ..config import Telegram


async def _make_mtproto_client(name: str, api_id: int, api_hash: str) -> Client:
    """
    Create and start a bare MTProto user-context client.
    Pyrogram will connect to Telegram DCs directly via the MTProto protocol
    using only the API credentials — no bot token, no session string.
    The auth key is negotiated fresh on every startup and kept in memory.
    """
    client = await Client(
        name=name,
        api_id=api_id,
        api_hash=api_hash,
        # No bot_token → user-context MTProto connection
        # no_updates   → never pulls the update queue, pure data channel
        no_updates=True,
        in_memory=True,          # auth key lives in RAM, nothing written to disk
        sleep_threshold=Telegram.SLEEP_THRESHOLD,
    ).start()
    me = await client.get_me()
    client.id = me.id
    logging.info("MTProto client '%s' connected as %s (id=%d)", name, me.first_name, me.id)
    return client


async def initialize_clients():
    # ── Account 1 → download client ───────────────────────────────────────
    dl = await _make_mtproto_client(
        name="dl_account",
        api_id=Telegram.API_ID,
        api_hash=Telegram.API_HASH,
    )

    # ── Account 2 → stream client ──────────────────────────────────────────
    str_ = await _make_mtproto_client(
        name="str_account",
        api_id=Telegram.API_ID_2,
        api_hash=Telegram.API_HASH_2,
    )

    # Wire into module globals
    _bot.dl_client  = dl
    _bot.str_client = str_

    _bot.multi_clients["dl"]     = dl
    _bot.multi_clients["stream"] = str_
    _bot.work_loads["dl"]        = 0
    _bot.work_loads["stream"]    = 0

    print(f"  Download MTProto : Account 1  id={dl.id}")
    print(f"  Stream   MTProto : Account 2  id={str_.id}")
