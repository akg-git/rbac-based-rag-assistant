from pathlib import Path
import duckdb


# -------------------------#
#    DuckDB Setup          #
# -------------------------#

# ensure directory for duckdb
DUCKDB_DIR = Path("static/data")
DUCKDB_DIR.mkdir(parents=True, exist_ok=True)

DUCKDB_PATH = DUCKDB_DIR / "structured_queries.duckdb"

# connect to DuckDB file (module-level so importing code gets connections)
duckdb_conn = duckdb.connect(str(DUCKDB_PATH))

def init_duckdb():
    duckdb_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tables_metadata (
                table_name TEXT,
                roles TEXT          
        )
        """
    )

def get_duckdb_conn():
    return duckdb_conn
