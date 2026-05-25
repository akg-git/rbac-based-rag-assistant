from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.authentication.hashing import verify_password
from app.schemas.sqlitedb import get_sqlite_conn

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    # print("username: ", username)
    # print("password: ", password)

    conn = get_sqlite_conn()
    c = conn.cursor()

    c.execute("SELECT password, role FROM users WHERE username = ?", (username,))
    row = c.fetchone()

    # print("DB row:", row)
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    stored_hash = row[0]

    if not verify_password(password, stored_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    return {"username": username, "role": row[1]}