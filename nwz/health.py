import os
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "nwz.sqlite"


def check() -> dict:
    db_path = str(_DB_PATH)
    db_exists = os.path.exists(db_path)
    article_count = 0
    edition_count = 0

    if db_exists:
        conn = sqlite3.connect(db_path)
        try:
            article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            edition_count = conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]
        finally:
            conn.close()

    return {
        "status": "ok",
        "db_path": db_path,
        "db_exists": db_exists,
        "article_count": article_count,
        "edition_count": edition_count,
    }
