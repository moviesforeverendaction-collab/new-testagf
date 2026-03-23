from os import cpu_count, environ as env
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    v = env.get(name)
    return int(v) if v not in (None, "") else default


def _opt_int(name: str) -> "int | None":
    v = env.get(name)
    return int(v) if v not in (None, "") else None


CPU_COUNT      = cpu_count() or 4
DEFAULT_WORKERS = max(64, min(CPU_COUNT * 4, 256))
TELEGRAM_MAX_CHUNK = 1024 * 1024  # Telegram hard ceiling


class Telegram:
    # ── Bot (commands only) ───────────────────────────────────────────────
    BOT_TOKEN = str(env.get("BOT_TOKEN", ""))
    API_ID    = int(env.get("API_ID",    0))
    API_HASH  = str(env.get("API_HASH",  ""))

    # ── Account 2 (MTProto, streaming via /watch) ─────────────────────────
    API_ID_2   = int(env.get("API_ID_2",   0))
    API_HASH_2 = str(env.get("API_HASH_2", ""))

    # ── General ───────────────────────────────────────────────────────────
    OWNER_ID        = int(env.get("OWNER_ID", 0))
    WORKERS         = _int("WORKERS", DEFAULT_WORKERS)
    DATABASE_URL    = str(env.get("DATABASE_URL", ""))
    SESSION_NAME    = str(env.get("SESSION_NAME", "FileStream"))
    UPDATES_CHANNEL = str(env.get("UPDATES_CHANNEL", ""))
    FORCE_SUB_ID    = env.get("FORCE_SUB_ID", None)
    FORCE_SUB       = str(env.get("FORCE_UPDATES_CHANNEL", "false")).lower() == "true"
    SLEEP_THRESHOLD = _int("SLEEP_THRESHOLD", 60)
    FILE_PIC        = env.get("FILE_PIC",   "https://graph.org/file/5bb9935be0229adf98b73.jpg")
    START_PIC       = env.get("START_PIC",  "https://graph.org/file/290af25276fa34fa8f0aa.jpg")
    VERIFY_PIC      = env.get("VERIFY_PIC", "https://graph.org/file/736e21cc0efa4d8c2a0e4.jpg")
    FLOG_CHANNEL    = _opt_int("FLOG_CHANNEL")
    ULOG_CHANNEL    = _opt_int("ULOG_CHANNEL")
    MODE            = env.get("MODE", "primary")
    SECONDARY       = MODE.lower() == "secondary"
    AUTH_USERS      = list(set(int(x) for x in str(env.get("AUTH_USERS", "")).split() if x))


class Server:
    PORT                  = _int("PORT", 8080)
    BIND_ADDRESS          = str(env.get("BIND_ADDRESS", "0.0.0.0"))
    PING_INTERVAL         = _int("PING_INTERVAL", 1200)
    STREAM_CHUNK_SIZE     = TELEGRAM_MAX_CHUNK          # always 1 MB
    STREAM_PREFETCH       = max(4, _int("STREAM_PREFETCH", 16))
    MEDIA_SESSION_POOL_SIZE = max(2, _int("MEDIA_SESSION_POOL_SIZE", 8))
    STREAM_MAX_RETRIES    = max(2, _int("STREAM_MAX_RETRIES", 5))
    FILE_ID_CACHE_TTL     = max(1800, _int("FILE_ID_CACHE_TTL", 86400))
    TCP_BACKLOG           = max(2048, _int("TCP_BACKLOG", 16384))
    REQUEST_MAX_SIZE      = _int("REQUEST_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    HAS_SSL  = str(env.get("HAS_SSL", "0")).lower() in ("1", "true", "yes")
    NO_PORT  = str(env.get("NO_PORT", "0")).lower() in ("1", "true", "yes")
    FQDN     = str(env.get("FQDN", BIND_ADDRESS))
    URL      = "http{}://{}{}/".format(
        "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
    )
