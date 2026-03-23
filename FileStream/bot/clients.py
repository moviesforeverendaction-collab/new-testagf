"""
Starts two MTProto bot clients using bot tokens — no phone prompts, no
session strings, no interactive auth ever. Bot tokens work headlessly
on any server.

dl_client  → BOT_TOKEN   + API_ID/API_HASH   → serves /dl  (downloads)
str_client → BOT_TOKEN_2 + API_ID_2/API_HASH_2 → serves /stream (streaming)

Both clients use no_updates=True — they are pure MTProto data channels.
The main FileStream bot (also BOT_TOKEN) handles commands separately.
"""
import logging
import FileStream.bot as _bot
from pyrogram import Client
from ..config import Telegram


async def _make_bot_mtproto(name: str, api_id: int, api_hash: str, bot_token: str) -> Client:
    """
    Create a headless MTProto client using a bot token.
    Pyrogram connects directly to Telegram DCs via MTProto protocol.
    No phone number, no session string, no interactive prompt — ever.
    """
    client = await Client(
        name=name,
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        no_updates=True,     # pure data channel — never pulls update queue
        in_memory=True,      # auth key in RAM, nothing written to disk
        sleep_threshold=Telegram.SLEEP_THRESHOLD,
    ).start()
    me = await client.get_me()
    client.id = me.id
    logging.info("MTProto client '%s' ready — @%s (id=%d)", name, me.username, me.id)
    return client


async def initialize_clients():
    # ── Account 1 → download client (BOT_TOKEN + API_ID/API_HASH) ────────
    dl = await _make_bot_mtproto(
        name="dl_client",
        api_id=Telegram.API_ID,
        api_hash=Telegram.API_HASH,
        bot_token=Telegram.BOT_TOKEN,
    )

    # ── Account 2 → stream client (BOT_TOKEN_2 + API_ID_2/API_HASH_2) ────
    # Falls back to BOT_TOKEN if BOT_TOKEN_2 not set
    bot_token_2 = Telegram.BOT_TOKEN_2 or Telegram.BOT_TOKEN
    str_ = await _make_bot_mtproto(
        name="str_client",
        api_id=Telegram.API_ID_2,
        api_hash=Telegram.API_HASH_2,
        bot_token=bot_token_2,
    )

    # Wire into module globals
    _bot.dl_client  = dl
    _bot.str_client = str_

    _bot.multi_clients["dl"]     = dl
    _bot.multi_clients["stream"] = str_
    _bot.work_loads["dl"]        = 0
    _bot.work_loads["stream"]    = 0

    print(f"  Download MTProto : @{getattr(dl,  'username', '?')}  (id={dl.id})")
    print(f"  Stream   MTProto : @{getattr(str_, 'username', '?')}  (id={str_.id})")
