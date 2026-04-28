from fastapi import APIRouter, Depends, Form, HTTPException
from app.authentication.auth import authenticate
from app.schemas.sqlitedb import get_sqlite_conn
from passlib.hash import bcrypt
import sqlite3

router = APIRouter()

# Login handler
@router.get("/login")
def login(user = Depends(authenticate)):
    return {
        "message": f"Welcome {user['username']}!",
        "role": user["role"]
    }

# Create a new user
@router.post("/create-user")
def create_user(
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form(...), 
    user = Depends(authenticate)
    ):

    if user["role"] != "C-Level":
        raise HTTPException(status_code=403, detail="Only C-Level can create users.")

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Check if role exists
    c.execute("SELECT 1 from roles WHERE role_name = ?", (role,))

    if not c.fetchone():
        raise HTTPException(status_code=400, detail="Invalid role specified.")
    
    # Hash password before storing
    hashed_password = bcrypt.hash(password)

    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                (username, hashed_password, role))
        conn.commit()

        return {"message": f"User '{username}' created with role '{role}'."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists.")
    finally:
        conn.close()

# create a new role
@router.post("/create-role")
def create_role(
    role_name: str = Form(...), 
    user = Depends(authenticate)
    ):

    if user['role'] != "C-Level":
        raise HTTPException(status_code=403, detail="Only C-Level can create roles.")
    
    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    try:
        c.execute("INSERT INTO roles (role_name) VALUES (?)", (role_name,))
        conn.commit()
        return {"message": f"Role '{role_name}' created successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Role already exists.")
    finally:
        conn.close()
