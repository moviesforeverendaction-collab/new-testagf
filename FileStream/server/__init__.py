from aiohttp import web
from FileStream.config import Server
from .stream_routes import routes

def web_server():
    web_app = web.Application(client_max_size=Server.REQUEST_MAX_SIZE)
    web_app.add_routes(routes)
    return web_app
