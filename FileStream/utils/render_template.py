import jinja2
import urllib.parse
from FileStream.config import Server
from FileStream.utils.database import Database
from FileStream.utils.human_readable import humanbytes

db = Database(Server.__dict__.get("DATABASE_URL", ""), "")

# Late import to avoid circular — resolved after app starts
def _db():
    from FileStream.config import Telegram
    return Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)

_db_instance = None

def get_db():
    global _db_instance
    if _db_instance is None:
        from FileStream.config import Telegram
        _db_instance = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)
    return _db_instance

template_env = jinja2.Environment(autoescape=True)


async def render_page(db_id: str) -> str:
    db       = get_db()
    file_data = await db.get_file(db_id)

    # /dl  → Account 1 MTProto  (download button)
    # /stream → Account 2 MTProto (video src inside player)
    dl_url     = urllib.parse.urljoin(Server.URL, f"dl/{db_id}")
    stream_url = urllib.parse.urljoin(Server.URL, f"stream/{db_id}")

    file_size = humanbytes(file_data["file_size"])
    file_name = file_data["file_name"].replace("_", " ")
    mime_root = str(file_data.get("mime_type") or "").split("/", 1)[0].strip()

    if mime_root == "video":
        template_file = "FileStream/template/play.html"
        # video src uses /stream (Account 2)
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
