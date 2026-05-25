from fastapi import APIRouter, Depends, Form, HTTPException
from app.authentication.auth import authenticate
from app.schemas.sqlitedb import get_sqlite_conn
from argon2.exceptions import VerifyMismatchError
from app.authentication.hashing import hash_password, verify_password
import sqlite3

router = APIRouter()

# Login handler
@router.get("/login")
def login(user = Depends(authenticate)):
    return {
        "message": f"Welcome {user['username']}!",
        "role": user["role"]
    }

@router.get("/roles")
def get_roles(user=Depends(authenticate)):

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    #fetch all roles from roles table
    c.execute("SELECT role_name FROM roles")
    roles = [r[0] for r in c.fetchall()]
    return {"roles": roles}

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
    hashed_password = hash_password(password)
    
    try:
        # PasswordHasher().verify(password, hashed_password)
        verify_password(password, hashed_password)
        print("✅ Password hashing and verification successful.")
    except VerifyMismatchError:
        print("❌ Invalid Password")

    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                (username, hashed_password, role))
        conn.commit()

        return {"message": f"User '{username}' created with role '{role}'."}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="User already exists.")
    # finally:
    #     conn.close()

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
        conn.rollback()
        raise HTTPException(status_code=400, detail="Role already exists.")
    # finally:
    #     conn.close()

# Logout handler
@router.get("/logout")
def logout(user = Depends(authenticate)):
    return {
        "message": f"Welcome {user['username']}!",
        "role": user["role"]
    }