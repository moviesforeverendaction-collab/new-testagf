import time
import math
import logging
import mimetypes
import traceback
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from FileStream.bot import multi_clients, work_loads, FileStream
from FileStream.config import Telegram, Server
from FileStream.exceptions import FIleNotFound, InvalidHash
from FileStream import utils, StartTime, __version__
from FileStream.utils.render_template import render_page

routes = web.RouteTableDef()

@routes.get("/status", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + FileStream.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": __version__,
        }
    )

@routes.get("/watch/{path}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        return web.Response(text=await render_page(path), content_type='text/html')
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass


@routes.get("/dl/{path}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        return await media_streamer(request, path)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        traceback.print_exc()
        logging.critical(e.with_traceback(None))
        logging.debug(traceback.format_exc())
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}


def _parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int]:
    if not range_header:
        return 0, file_size - 1

    try:
        units, _, value = range_header.partition("=")
        if units.strip().lower() != "bytes" or not value or "," in value:
            raise ValueError("Unsupported range header")

        start_str, end_str = value.split("-", 1)
        start_str = start_str.strip()
        end_str = end_str.strip()

        if not start_str and not end_str:
            raise ValueError("Invalid range header")

        if not start_str:
            length = int(end_str)
            if length <= 0:
                raise ValueError("Invalid suffix range")
            return max(file_size - length, 0), file_size - 1

        from_bytes = int(start_str)
        until_bytes = int(end_str) if end_str else file_size - 1
        return from_bytes, until_bytes
    except (TypeError, ValueError):
        raise web.HTTPRequestRangeNotSatisfiable(
            headers={"Content-Range": f"bytes */{file_size}"}
        )

async def media_streamer(request: web.Request, db_id: str):
    range_header = request.headers.get("Range")
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if Telegram.MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.headers.get('X-FORWARDED-FOR',request.remote)}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(db_id, multi_clients)
    logging.debug("after calling get_file_properties")
    
    file_size = file_id.file_size

    from_bytes, until_bytes = _parse_range_header(range_header, file_size)

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = Server.STREAM_CHUNK_SIZE
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.floor(until_bytes / chunk_size) - math.floor(offset / chunk_size) + 1

    mime_type = file_id.mime_type
    file_name = utils.get_name(file_id)
    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # if "video/" in mime_type or "audio/" in mime_type:
    #     disposition = "inline"

    headers = {
        "Content-Type": f"{mime_type}",
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Length": str(req_length),
        "Content-Disposition": f'{disposition}; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    if request.method == "HEAD":
        return web.Response(
            status=206 if range_header else 200,
            headers=headers,
        )

    body = tg_connect.yield_file(
        db_id,
        multi_clients,
        file_id,
        index,
        offset,
        first_part_cut,
        last_part_cut,
        part_count,
        chunk_size,
    )

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers=headers,
    )
