from pathlib import Path
from typing import Dict, List, Optional
import duckdb


# -------------------------#
#    DuckDB Setup          #
# -------------------------#

# ensure directory for duckdb
DUCKDB_DIR = Path("static/data")
DUCKDB_DIR.mkdir(parents=True, exist_ok=True)

DUCKDB_PATH = DUCKDB_DIR / "structured_queries.duckdb"

def get_duckdb_conn(read_only: bool = False):
    """Open a controlled DuckDB connection for one operation or request."""
    return duckdb.connect(str(DUCKDB_PATH), read_only=read_only)


def init_duckdb():
    """Initialize DuckDB and close the setup connection immediately."""
    conn = get_duckdb_conn()
    try:
        conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tables_metadata (
                table_name TEXT,
                role TEXT
        )
        """
        )
    finally:
        conn.close()


def close_duckdb():
    """Retained for application shutdown compatibility.

    Connections are owned and closed by the operation that opens them.
    """
    return None


def get_duckdb_schema(
    conn,
    allowed_tables: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """Return catalog-backed table/column metadata, optionally filtered."""
    rows = conn.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
                WHERE table_schema = 'main'
                    AND table_name <> 'tables_metadata'
        ORDER BY table_name, ordinal_position
        """
    ).fetchall()
    allowed = {str(table).casefold() for table in allowed_tables or []}
    schema: Dict[str, List[str]] = {}
    for table_name, column_name in rows:
        if allowed and table_name.casefold() not in allowed:
            continue
        schema.setdefault(table_name, []).append(column_name)
    return schema
