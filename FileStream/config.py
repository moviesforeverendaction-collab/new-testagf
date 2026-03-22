from os import cpu_count, environ as env
from dotenv import load_dotenv

load_dotenv()


def _get_int_env(name: str, default: int) -> int:
    value = env.get(name)
    if value in (None, ""):
        return default
    return int(value)


def _get_optional_int_env(name: str) -> int | None:
    value = env.get(name)
    if value in (None, ""):
        return None
    return int(value)


CPU_COUNT = cpu_count() or 15
DEFAULT_WORKERS = max(32, CPU_COUNT * 15)
TELEGRAM_MAX_STREAM_CHUNK = 1024 * 1024

class Telegram:
    API_ID = int(env.get("API_ID"))
    API_HASH = str(env.get("API_HASH"))
    BOT_TOKEN = str(env.get("BOT_TOKEN"))
    OWNER_ID = int(env.get('OWNER_ID', ''))
    WORKERS = _get_int_env("WORKERS", DEFAULT_WORKERS)
    DATABASE_URL = str(env.get('DATABASE_URL'))
    UPDATES_CHANNEL = str(env.get('UPDATES_CHANNEL', "Telegram"))
    SESSION_NAME = str(env.get('SESSION_NAME', 'FileStream'))
    FORCE_SUB_ID = env.get('FORCE_SUB_ID', None)
    FORCE_SUB = env.get('FORCE_UPDATES_CHANNEL', False)
    FORCE_SUB = True if str(FORCE_SUB).lower() == "true" else False
    SLEEP_THRESHOLD = int(env.get("SLEEP_THRESHOLD", "60"))
    FILE_PIC = env.get('FILE_PIC', "https://graph.org/file/5bb9935be0229adf98b73.jpg")
    START_PIC = env.get('START_PIC', "https://graph.org/file/290af25276fa34fa8f0aa.jpg")
    VERIFY_PIC = env.get('VERIFY_PIC', "https://graph.org/file/736e21cc0efa4d8c2a0e4.jpg")
    MULTI_CLIENT = False
    FLOG_CHANNEL = _get_optional_int_env("FLOG_CHANNEL")   # Logs channel for file logs
    ULOG_CHANNEL = _get_optional_int_env("ULOG_CHANNEL")   # Logs channel for user logs
    MODE = env.get("MODE", "primary")
    SECONDARY = True if MODE.lower() == "secondary" else False
    AUTH_USERS = list(set(int(x) for x in str(env.get("AUTH_USERS", "")).split()))

class Server:
    PORT = int(env.get("PORT", 8080))
    BIND_ADDRESS = str(env.get("BIND_ADDRESS", "0.0.0.0"))
    PING_INTERVAL = int(env.get("PING_INTERVAL", "1200"))
    STREAM_CHUNK_SIZE = max(
        64 * 1024,
        min(_get_int_env("STREAM_CHUNK_SIZE", TELEGRAM_MAX_STREAM_CHUNK), TELEGRAM_MAX_STREAM_CHUNK),
    )
    STREAM_PREFETCH = max(8, _get_int_env("STREAM_PREFETCH", max(16, CPU_COUNT * 4)))
    FILE_ID_CACHE_TTL = max(30 * 60, _get_int_env("FILE_ID_CACHE_TTL", 24 * 60 * 60))
    TCP_BACKLOG = max(1024, _get_int_env("TCP_BACKLOG", 8192))
    REQUEST_MAX_SIZE = max(30_000_000, _get_int_env("REQUEST_MAX_SIZE", 2 * 1024 * 1024 * 1024))
    HAS_SSL = str(env.get("HAS_SSL", "0").lower()) in ("1", "true", "t", "yes", "y")
    NO_PORT = str(env.get("NO_PORT", "0").lower()) in ("1", "true", "t", "yes", "y")
    FQDN = str(env.get("FQDN", BIND_ADDRESS))
    URL = "http{}://{}{}/".format(
        "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
    )
