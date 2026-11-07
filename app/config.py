import os
from pathlib import Path
from urllib.parse import quote

ENV_FILE = Path(__file__).resolve().parent.parent / "1.env"


def load_env_file(path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def text(name):
    return os.environ[name]


def number(name):
    return int(os.environ[name])


load_env_file(ENV_FILE)

POSTGRES_USER = text("POSTGRES_USER")
POSTGRES_PASSWORD = text("POSTGRES_PASSWORD")
POSTGRES_DB = text("POSTGRES_DB")
DB_HOST = text("DB_HOST")
DB_PORT = number("DB_PORT")
DB_POOL_MIN = number("DB_POOL_MIN")
DB_POOL_MAX = number("DB_POOL_MAX")
DATABASE_URL = (
    f"postgresql://{quote(POSTGRES_USER, safe='')}:{quote(POSTGRES_PASSWORD, safe='')}"
    f"@{DB_HOST}:{DB_PORT}/{quote(POSTGRES_DB, safe='')}"
)

SESSION_COOKIE = text("SESSION_COOKIE")
SESSION_DAYS = number("SESSION_DAYS")
LOGIN_MIN = number("LOGIN_MIN")
LOGIN_MAX = number("LOGIN_MAX")
PASSWORD_MIN = number("PASSWORD_MIN")
PASSWORD_MAX = number("PASSWORD_MAX")
LOGIN_ATTEMPTS = number("LOGIN_ATTEMPTS")
LOGIN_WINDOW = number("LOGIN_WINDOW")

CANVAS_TITLE_MAX = number("CANVAS_TITLE_MAX")
CANVAS_DEFAULT_TITLE = text("CANVAS_DEFAULT_TITLE")
SHARE_CODE_BYTES = number("SHARE_CODE_BYTES")

MAX_BLOCKS = number("MAX_BLOCKS")
MAX_TEXT = number("MAX_TEXT")
MAX_LABEL = number("MAX_LABEL")
MAX_COORD = number("MAX_COORD")
BLOCK_SIZE_MIN = number("BLOCK_SIZE_MIN")
BLOCK_SIZE_MAX = number("BLOCK_SIZE_MAX")
UNDO_LIMIT = number("UNDO_LIMIT")
SEND_TIMEOUT = number("SEND_TIMEOUT")
