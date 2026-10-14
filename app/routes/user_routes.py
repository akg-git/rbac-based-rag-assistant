from fastapi import APIRouter, Depends, Form, HTTPException
from app.authentication.auth import authenticate
from app.schemas.sqlitedb import get_sqlite_conn
from argon2.exceptions import VerifyMismatchError
from app.authentication.hashing import hash_password, verify_password
from app.utils.audit_context import AuditContext, get_audit_context
import sqlite3

router = APIRouter()

# Login handler
@router.get("/login")
def login(audit: AuditContext = Depends(get_audit_context)):
    audit.emit(
        action="auth.login",
        resource="authentication",
        authorization_decision="allowed",
        result="success",
        outcome_status="authorized",
    )
    return {
        "message": f"Welcome {audit.username}!",
        "role": audit.role
    }

@router.get("/roles")
def get_roles(audit: AuditContext = Depends(get_audit_context)):

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    #fetch all roles from roles table
    c.execute("SELECT role_name FROM roles")
    roles = [r[0] for r in c.fetchall()]
    audit.emit(
        action="role.read",
        resource="roles",
        authorization_decision="allowed",
        result="success",
        outcome_status="authorized",
    )
    return {"roles": roles}

@router.get("/user-info/{username}")
def get_user(username: str, audit: AuditContext = Depends(get_audit_context)):

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Fetch user information by username
    c.execute("SELECT username, role FROM users WHERE username = ?", (username,))
    user_info = c.fetchone()
    
    if not user_info:
        audit.emit(
            action="user.read",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

    audit.emit(
        action="user.read",
        resource=f"user:{username}",
        authorization_decision="allowed",
        result="success",
        outcome_status="authorized",
    )
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
    audit: AuditContext = Depends(get_audit_context)
    ):

    if audit.role != "C-Level":
        audit.emit(
            action="user.create",
            resource=f"user:{username}",
            authorization_decision="denied",
            result="failure",
            outcome_status="denied",
        )
        raise HTTPException(status_code=403, detail="Only C-Level can create users.")

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Check if role exists
    c.execute("SELECT 1 from roles WHERE role_name = ?", (role,))

    if not c.fetchone():
        audit.emit(
            action="user.create",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
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
        audit.emit(
            action="user.create",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
        )
        return {"message": f"User '{username}' created with role '{role}'."}
    except sqlite3.IntegrityError:
        conn.rollback()
        audit.emit(
            action="user.create",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
        raise HTTPException(status_code=400, detail="User already exists.")
    # finally:
    #     conn.close()

# Delete a user
@router.post("/delete-user")
def delete_user(
    username: str = Form(...), 
    role: str = Form(...), 
    audit: AuditContext = Depends(get_audit_context)
    ):

    if audit.role != "C-Level":
        audit.emit(
            action="user.delete",
            resource=f"user:{username}",
            authorization_decision="denied",
            result="failure",
            outcome_status="denied",
        )
        raise HTTPException(status_code=403, detail="Only C-Level can delete users.")

    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    # Check if user exists
    c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    
    if not c.fetchone():
        audit.emit(
            action="user.delete",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

    try:
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        audit.emit(
            action="user.delete",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
        )
        return {"message": f"User '{username}' (Role: {role}) deleted successfully."}
    except sqlite3.Error as e:
        conn.rollback()
        audit.emit(
            action="user.delete",
            resource=f"user:{username}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
    # finally:
    #     conn.close()

# create a new role
@router.post("/create-role")
def create_role(
    role_name: str = Form(...), 
    audit: AuditContext = Depends(get_audit_context)
    ):

    if audit.role != "C-Level":
        audit.emit(
            action="role.create",
            resource=f"role:{role_name}",
            authorization_decision="denied",
            result="failure",
            outcome_status="denied",
        )
        raise HTTPException(status_code=403, detail="Only C-Level can create roles.")
    
    # Get a cursor for the SQLite connection
    conn = get_sqlite_conn()
    c = conn.cursor()

    try:
        c.execute("INSERT INTO roles (role_name) VALUES (?)", (role_name,))
        conn.commit()
        audit.emit(
            action="role.create",
            resource=f"role:{role_name}",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
        )
        return {"message": f"Role '{role_name}' created successfully."}
    except sqlite3.IntegrityError:
        conn.rollback()
        audit.emit(
            action="role.create",
            resource=f"role:{role_name}",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
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