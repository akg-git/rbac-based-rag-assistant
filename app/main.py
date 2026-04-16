
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

app = FastAPI()
security = HTTPBasic()
load_dotenv()

# Initialize DB connections at module level
get_duckdb_conn()
get_sqlite_conn()

print("DB initialized successfully")

# Model request
class ChatRequest(BaseModel):
    question: str