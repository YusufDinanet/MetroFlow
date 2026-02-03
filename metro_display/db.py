"""SQLite helper."""
import sqlite3
from pathlib import Path
from typing import Optional, Sequence

from . import config


def get_connection(path: Optional[Path] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def query(conn: sqlite3.Connection, sql: str, params: Sequence = ()):  # noqa: ANN001
    cur = conn.execute(sql, params)
    return cur.fetchall()
