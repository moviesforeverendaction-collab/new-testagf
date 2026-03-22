import jinja2
import urllib.parse
from FileStream.config import Telegram, Server
from FileStream.utils.database import Database
from FileStream.utils.human_readable import humanbytes

db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)
template_env = jinja2.Environment(autoescape=True)


async def render_page(db_id):
    file_data = await db.get_file(db_id)
    src = urllib.parse.urljoin(Server.URL, f'dl/{file_data["_id"]}')
    file_size = humanbytes(file_data['file_size'])
    file_name = file_data['file_name'].replace("_", " ")
    mime_root = str(file_data.get('mime_type') or '').split('/', 1)[0].strip()

    if mime_root == 'video':
        template_file = "FileStream/template/play.html"
    else:
        template_file = "FileStream/template/dl.html"

    with open(template_file, encoding="utf-8") as handle:
        template = template_env.from_string(handle.read())

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        mime_type=file_data.get('mime_type') or 'video/mp4'
    )
