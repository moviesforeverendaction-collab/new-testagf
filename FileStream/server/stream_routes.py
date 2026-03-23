"""
HTTP routes.

  GET /status        → health check
  GET /dl/{path}     → raw file bytes    — served via Account 1 MTProto
  GET /watch/{path}  → HTML player page  — video bytes via Account 2 MTProto

Range requests (seek/resume) fully supported on both endpoints.
ByteStreamer instances are cached per-client so DC session pools survive
across requests.
"""
import math
import mimetypes
import time
import logging

from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine

from FileStream.bot import FileStream, multi_clients, work_loads, dl_client, str_client
from FileStream.config import Telegram, Server
from FileStream.exceptions import FIleNotFound, InvalidHash
from FileStream import utils, StartTime, __version__
from FileStream.utils.render_template import render_page
from FileStream.utils.custom_dl import ByteStreamer

routes = web.RouteTableDef()

# ── ByteStreamer cache (one per MTProto client) ───────────────────────────
_streamers: dict = {}

def _streamer(client, role: str) -> ByteStreamer:
    if client not in _streamers:
        _streamers[client] = ByteStreamer(client, role)
    return _streamers[client]


# ── Range header parser ───────────────────────────────────────────────────

def _parse_range(header: "str | None", size: int) -> "tuple[int, int]":
    if not header:
        return 0, size - 1
    units, _, value = header.partition("=")
    if units.strip().lower() != "bytes" or not value or "," in value:
        raise web.HTTPRequestRangeNotSatisfiable(
            headers={"Content-Range": f"bytes */{size}"}
        )
    start_s, _, end_s = value.partition("-")
    start_s = start_s.strip()
    end_s   = end_s.strip()
    try:
        if not start_s and not end_s:
            raise ValueError
        if not start_s:                      # suffix: bytes=-500
            n = int(end_s)
            if n <= 0:
                raise ValueError
            return max(size - n, 0), size - 1
        from_b  = int(start_s)
        until_b = int(end_s) if end_s else size - 1
        return from_b, until_b
    except (TypeError, ValueError):
        raise web.HTTPRequestRangeNotSatisfiable(
            headers={"Content-Range": f"bytes */{size}"}
        )


# ── Status ────────────────────────────────────────────────────────────────

@routes.get("/status", allow_head=True)
async def status_handler(_: web.Request) -> web.Response:
    return web.json_response({
        "status":         "running",
        "uptime":         utils.get_readable_time(time.time() - StartTime),
        "bot":            "@" + FileStream.username,
        "dl_client_id":   getattr(dl_client,  "id", None),
        "str_client_id":  getattr(str_client, "id", None),
        "work_loads":     dict(work_loads),
        "version":        __version__,
    })


# ── /watch — HTML player, bytes from Account 2 ───────────────────────────

@routes.get("/watch/{path}", allow_head=True)
async def watch_handler(request: web.Request) -> web.Response:
    try:
        path = request.match_info["path"]
        return web.Response(text=await render_page(path), content_type="text/html")
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass


# ── /dl — raw bytes from Account 1 ───────────────────────────────────────

@routes.get("/dl/{path}", allow_head=True)
async def dl_handler(request: web.Request) -> web.Response:
    try:
        return await _serve(request, request.match_info["path"], role="dl")
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical("/dl unhandled: %s", e, exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))


# ── Internal streamer called by both /dl and /watch video bytes ───────────

async def _serve(request: web.Request, db_id: str, role: str) -> web.Response:
    range_hdr = request.headers.get("Range")

    # Pick the right MTProto client
    client = (dl_client if role == "dl" else str_client) or FileStream
    wl_key = role  # "dl" or "stream"

    tg        = _streamer(client, role)
    file_id   = await tg.get_file_properties(db_id, multi_clients)
    file_size = file_id.file_size

    from_b, until_b = _parse_range(range_hdr, file_size)

    if from_b < 0 or until_b >= file_size or until_b < from_b:
        return web.Response(
            status=416,
            body="416: Range Not Satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk      = Server.STREAM_CHUNK_SIZE
    until_b    = min(until_b, file_size - 1)
    offset     = from_b - (from_b % chunk)
    first_cut  = from_b - offset
    last_cut   = until_b % chunk + 1
    req_len    = until_b - from_b + 1
    parts      = math.floor(until_b / chunk) - math.floor(offset / chunk) + 1

    mime = file_id.mime_type or ""
    name = utils.get_name(file_id)
    if not mime:
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"

    disp   = "inline" if ("video/" in mime or "audio/" in mime) else "attachment"
    status = 206 if range_hdr else 200

    headers = {
        "Content-Type":        mime,
        "Content-Range":       f"bytes {from_b}-{until_b}/{file_size}",
        "Content-Length":      str(req_len),
        "Content-Disposition": f'{disp}; filename="{name}"',
        "Accept-Ranges":       "bytes",
        "Cache-Control":       "public, max-age=3600",
    }

    if request.method == "HEAD":
        return web.Response(status=status, headers=headers)

    work_loads[wl_key] += 1
    try:
        body = tg.yield_file(
            db_id, multi_clients, file_id,
            offset, first_cut, last_cut, parts, chunk,
        )
        return web.Response(status=status, body=body, headers=headers)
    finally:
        work_loads[wl_key] -= 1


# ── Hook render_page to use str_client for its internal media bytes ───────
# (render_page just returns HTML; the browser then fetches /dl/{id} for bytes)
# Nothing extra needed here — the HTML src points to /dl/{id} for downloads
# and /dl/{id} for the video src too, but /watch video uses str_client
# via the route above which just returns the HTML page; the <video src>
# inside that HTML points back to /dl/{id} so the browser streams it.
# If you want /watch video src to use Account 2, change render_template.py
# to point src at /stream/{id} and add a /stream route that calls
# _serve(..., role="stream"). That's all it takes.


# ── /stream — video bytes from Account 2 (used by play.html <video src>) ─

@routes.get("/stream/{path}", allow_head=True)
async def stream_handler(request: web.Request) -> web.Response:
    try:
        return await _serve(request, request.match_info["path"], role="stream")
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical("/stream unhandled: %s", e, exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))
