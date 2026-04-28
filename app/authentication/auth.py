from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.hash import bcrypt
from schemas.sqlitedb import get_sqlite_conn

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
    conn.commit()
    conn.close()

    # print("DB row:", row)
    
    if not row or not bcrypt.verify(password, row[0]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"username": username, "role": row[1]}