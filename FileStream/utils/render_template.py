import jinja2
import urllib.parse

template_env = jinja2.Environment(autoescape=True)

_db = None

def _get_db():
    global _db
    if _db is None:
        from FileStream.config import Telegram
        from FileStream.utils.database import Database
        _db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)
    return _db


async def render_page(db_id: str) -> str:
    from FileStream.config import Server
    from FileStream.utils.human_readable import humanbytes

    db        = _get_db()
    file_data = await db.get_file(db_id)

    dl_url     = urllib.parse.urljoin(Server.URL, f"dl/{db_id}")
    stream_url = urllib.parse.urljoin(Server.URL, f"stream/{db_id}")

    file_size = humanbytes(file_data["file_size"])
    file_name = file_data["file_name"].replace("_", " ")
    mime_root = str(file_data.get("mime_type") or "").split("/", 1)[0].strip()

    if mime_root == "video":
        template_file = "FileStream/template/play.html"
        src = stream_url
    else:
        template_file = "FileStream/template/dl.html"
        src = dl_url

    with open(template_file, encoding="utf-8") as fh:
        template = template_env.from_string(fh.read())

    return template.render(
        file_name=file_name,
        file_url=src,
        dl_url=dl_url,
        file_size=file_size,
        mime_type=file_data.get("mime_type") or "video/mp4",
    )
