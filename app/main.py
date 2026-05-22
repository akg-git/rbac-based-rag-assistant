from dotenv import load_dotenv
from fastapi import FastAPI
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# import DB connections from central module (initialises on import)
from app.schemas.duckdb import (
    init_duckdb,
    get_duckdb_conn
)

from app.schemas.sqlitedb import (
    init_sqlite,
    get_sqlite_conn
)

# Import all routers
from app.routes.document_routes import router as document_router
from app.routes.user_routes import router as user_router
from app.routes.chat_routes import router as chat_router

app = FastAPI()

load_dotenv()

@app.on_event("startup")
def startup():
    init_duckdb()
    init_sqlite()
    print("DB initialized successfully")

# Register routers with the app
app.include_router(document_router, tags=["Documents"])
app.include_router(user_router, tags=["Users"])
app.include_router(chat_router, tags=["Chat"])

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on app shutdown"""
    get_sqlite_conn().close()
    get_duckdb_conn().close()
    print("✅ SQLite and DuckDB connections closed")