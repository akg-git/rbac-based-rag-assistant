import sqlite3
from pathlib import Path
from app.authentication.hashing import hash_password, verify_password
from argon2.exceptions import VerifyMismatchError, InvalidHashError

# SQLite setup
# SQLITE_DB_PATH = Path("app\\schemas\\roles_docs.db")
SQLITE_DB_PATH = Path("app") / "schemas" / "roles_docs.db"
sqlite_conn = sqlite3.connect(str(SQLITE_DB_PATH), check_same_thread=False, timeout=10.0)

def init_sqlite(conn: sqlite3.Connection = sqlite_conn) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
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
def create_default_user(conn: sqlite3.Connection = sqlite_conn) -> None:
    cur = conn.cursor()

    cur.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", ("C-Level",))
    
    password = "admin123"
    hashed_pw = hash_password(password)
    
    try:
        verify_password(password, hashed_pw)
        print("✅ Password hashing and verification successful.")
    except VerifyMismatchError:
        print("Hased Password:", hashed_pw)
        print("❌ Invalid Password")
    except InvalidHashError as ihe:
        print("Hased Password:", hashed_pw)
        print(f"❌ Invalid hash error: {ihe}")
    except Exception as e:
        print(f"❌ Error during password hashing: {type(e).__name__}: {e}")
        return

    try:
        cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", hashed_pw, "C-Level"))
        conn.commit()
        print("✅ Default C-Level user created.")
    except sqlite3.IntegrityError:
        print("⚠️ Default User already exists.")
    except Exception as e:
        print(f"❌ Error creating default user: {type(e).__name__}: {e}")
        conn.rollback()


# initialize sqlite schema at import time
init_sqlite()

# create default user at import time
create_default_user()



def get_sqlite_conn() -> sqlite3.Connection:
    return sqlite_conn


def get_sqlite_cursor() -> sqlite3.Cursor:
    return sqlite_conn.cursor()
