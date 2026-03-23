"""
FileStream v2 — entry point.

One bot  (BOT_TOKEN) handles commands.
Two bare MTProto clients handle media:
  dl_client  (Account 1) → /dl
  str_client (Account 2) → /stream  (video src in play.html)
"""
import sys
import asyncio
import contextlib
import logging
import logging.handlers
import traceback

from aiohttp import web
from pyrogram import idle

from FileStream.bot import FileStream
from FileStream.bot.clients import initialize_clients
from FileStream.config import Telegram, Server
from FileStream.server import web_server

logging.basicConfig(
    level=logging.INFO,
    datefmt="%d/%m/%Y %H:%M:%S",
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            "streambot.log", mode="a",
            maxBytes=50 * 1024 * 1024, backupCount=3, encoding="utf-8",
        ),
    ],
)
for _lib in ("aiohttp", "aiohttp.web", "pyrogram", "motor"):
    logging.getLogger(_lib).setLevel(logging.WARNING)

_runner = web.AppRunner(web_server(), access_log=None)


async def start_services():
    mode = "Secondary" if Telegram.SECONDARY else "Primary"
    print()
    print("═" * 60)
    print(f"  FileStream v2  │  {mode} mode")
    print("═" * 60)

    print("  [1/3] Starting bot…")
    await FileStream.start()
    me = await FileStream.get_me()
    FileStream.id       = me.id
    FileStream.username = me.username
    FileStream.fname    = me.first_name
    print(f"        Bot: @{me.username}  (DC {me.dc_id})")

    print("  [2/3] Starting MTProto clients…")
    await initialize_clients()

    print("  [3/3] Starting web server…")
    await _runner.setup()
    await web.TCPSite(
        _runner,
        Server.BIND_ADDRESS,
        Server.PORT,
        backlog=Server.TCP_BACKLOG,
        reuse_address=True,
        reuse_port=True,
    ).start()

    print()
    print("═" * 60)
    print(f"  URL              : {Server.URL}")
    print(f"  /dl   → Account 1 MTProto  (downloads)")
    print(f"  /stream → Account 2 MTProto  (streaming)")
    print(f"  Workers          : {Telegram.WORKERS}")
    print(f"  Chunk size       : {Server.STREAM_CHUNK_SIZE // 1024} KB")
    print(f"  Prefetch         : {Server.STREAM_PREFETCH} chunks")
    print(f"  DC sessions/pool : {Server.MEDIA_SESSION_POOL_SIZE}")
    print(f"  TCP backlog      : {Server.TCP_BACKLOG}")
    print("═" * 60)
    print()

    await idle()


async def cleanup():
    print("Shutting down…")
    await _runner.cleanup()
    with contextlib.suppress(Exception):
        await FileStream.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.error("Fatal:\n%s", traceback.format_exc())
    finally:
        loop.run_until_complete(cleanup())
        loop.stop()
        print("Stopped.")
