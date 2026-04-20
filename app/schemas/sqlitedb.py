import sqlite3
from pathlib import Path

import bcrypt

# SQLite setup
SQLITE_DB_PATH = Path("app\\schemas\\roles_docs.db")
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


# create default C-Level user for testing/demo purposes
def create_default_user():
    conn_local = sqlite3.connect("app\\schemas\\roles_docs.db")
    c_local = conn_local.cursor()

    c_local.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", ("C-Level",))
    # hashed_pw = bcrypt.hashpw("admin123", bcrypt.gensalt()).decode('utf-8')
    hashed_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(bcrypt.checkpw("admin123".encode('utf-8'), hashed_pw.encode('utf-8')))  # Test checkpw
    try:
        c_local.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", hashed_pw, "C-Level"))
        conn_local.commit()
        print("✅ Default C-Level user created.")
    except sqlite3.IntegrityError:
        print("⚠️ User already exists.")
    conn_local.close()


# initialize sqlite schema at import time
_init_sqlite()

# create default user at import time
create_default_user()



def get_sqlite_conn() -> sqlite3.Connection:
    return sqlite_conn


def get_sqlite_cursor() -> sqlite3.Cursor:
    return sqlite_conn.cursor()
