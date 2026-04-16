import sqlite3
from pathlib import Path

# SQLite setup
SQLITE_DB_PATH = Path("roles_docs.db")
sqlite_conn = sqlite3.connect(str(SQLITE_DB_PATH), check_same_thread=False)

def _init_sqlite(conn: sqlite3.Connection = sqlite_conn) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            role TEXT NOT NULL,
            headers_str TEXT,
            embedded INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()
    # keep module-level connection open for app reuse


# initialize sqlite schema at import time
_init_sqlite()


def get_sqlite_conn() -> sqlite3.Connection:
    return sqlite_conn


def get_sqlite_cursor() -> sqlite3.Cursor:
    return sqlite_conn.cursor()
