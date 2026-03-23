# FileStream v2 — Railway Edition

High-performance Telegram media streaming bot with **dual-account support**, optimised for Railway (32 vCPU / 32 GB RAM).

## Features

| Feature | Detail |
|---|---|
| Dual-account pools | Account 1 for streaming, Account 2 for downloading |
| Session pool per DC | 8 parallel DC connections per client (configurable) |
| Prefetch pipeline | 16-chunk async lookahead (no stall between chunks) |
| Range requests | Full seek/resume support (206 Partial Content) |
| File-ref auto-refresh | Transparent retry on expired Telegram file references |
| Multi-token support | Add unlimited extra bots via `MULTI_TOKEN1`, `MULTI_TOKEN2`… |
| Railway-native | `SO_REUSEPORT`, high TCP backlog, `/status` healthcheck |

## Environment Variables

Copy `.env.example` → `.env` and fill in your values.

### Required

| Variable | Description |
|---|---|
| `API_ID` | Telegram API ID (my.telegram.org) |
| `API_HASH` | Telegram API hash |
| `BOT_TOKEN` | Bot token from @BotFather |
| `DATABASE_URL` | MongoDB connection string |
| `OWNER_ID` | Your Telegram user ID |

### Dual-account (recommended for speed)

| Variable | Description |
|---|---|
| `API_ID_2` | Second account's API ID |
| `API_HASH_2` | Second account's API hash |
| `SESSION_STRING_2` | Pyrogram session string for second account |

Generate a session string:
```bash
pip install pyrofork
python -c "
from pyrogram import Client
with Client('gen', api_id=API_ID_2, api_hash=API_HASH_2) as c:
    print(c.export_session_string())
"
```

### Performance tuning (defaults are optimal for Railway 32 vCPU)

| Variable | Default | Description |
|---|---|---|
| `STREAM_PREFETCH` | 16 | Chunks to prefetch ahead |
| `MEDIA_SESSION_POOL_SIZE` | 8 | DC sessions per client |
| `WORKERS` | 128 | Pyrogram async workers |
| `STREAM_MAX_RETRIES` | 5 | Retry count on errors |

### Hosting

| Variable | Description |
|---|---|
| `FQDN` | Your Railway domain, e.g. `mybot.up.railway.app` |
| `HAS_SSL` | `true` if using HTTPS |
| `NO_PORT` | `true` to omit port from URLs |

## Deploy to Railway

1. Fork / upload this repo
2. Add all env variables in Railway dashboard
3. Railway will auto-detect `Dockerfile` and deploy
4. The `/status` endpoint is used as healthcheck

## Architecture

```
User request (/dl/...)
       │
       ▼
stream_routes.py  ─── pick least-loaded client from dl_clients pool
       │
       ▼
ByteStreamer.yield_file()
  ├── Session pool for this DC (8 sessions)
  ├── Prefetch pipeline (16 chunks ahead)
  └── Auto-retry on file reference expiry
       │
       ▼
aiohttp streaming response (206 Partial Content)
```
