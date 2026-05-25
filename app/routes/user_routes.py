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

@router.get("/user-info/{username}")
def get_user(username: str, user = Depends(authenticate)):

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Fetch user information by username
    c.execute("SELECT username, role FROM users WHERE username = ?", (username,))
    user_info = c.fetchone()
    
    if not user_info:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")
    
    return {
        "username": user_info[0],
        "role": user_info[1]
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

# Delete a user
@router.post("/delete-user")
def delete_user(
    username: str = Form(...), 
    role: str = Form(...), 
    user = Depends(authenticate)
    ):

    if user["role"] != "C-Level":
        raise HTTPException(status_code=403, detail="Only C-Level can delete users.")

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Check if user exists
    c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    
    if not c.fetchone():
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

    try:
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()

        return {"message": f"User '{username}' (Role: {role}) deleted successfully."}
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
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