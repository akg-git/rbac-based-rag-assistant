
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.security import HTTPBasic
from pydantic import BaseModel

# import DB connections from central module (initialises on import)
from app.schemas.duckdb import (
    get_duckdb_conn,
)

from app.schemas.sqlitedb import (
    get_sqlite_conn,
)

# Import all routers
from app.routes.document_routes import router as document_router
from app.routes.user_routes import router as user_router
from app.routes.chat_routes import router as chat_router

app = FastAPI()
security = HTTPBasic()
load_dotenv()

# Initialize DB connections at module level
get_duckdb_conn()
get_sqlite_conn()

print("DB initialized successfully")

# Register routers with the app
app.include_router(document_router, tags=["Documents"])
app.include_router(user_router, tags=["Users"])
app.include_router(chat_router, tags=["Chat"])

# Model request
class ChatRequest(BaseModel):
    question: str