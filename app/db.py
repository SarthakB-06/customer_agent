import sqlite3
from contextlib import contextmanager

from app.config import get_settings


@contextmanager
def connect():
    """Open a connection that commits on success and rolls back on any error."""
    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()