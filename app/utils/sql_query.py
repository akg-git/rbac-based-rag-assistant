import os
import tabulate
from app.schemas.duckdb import get_duckdb_conn
from app.schemas.sqlitedb import get_sqlite_conn
from groq import Groq
from pathlib import Path
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR,"app","schemas", "roles_docs.db")

#duckdb connection
duck_conn = get_duckdb_conn()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_allowed_tables_for_role(role:str) -> list[str]:

    role = role.lower()

    if role == "c-level":
        query = "SELECT table_name FROM tables_metadata"
        return [ row[0] for row in duck_conn.execute(query).fetchall()]
    
    elif role == "general":
        query = "SELECT table_name FROM tables_metadata WHERE role = 'general'"
        return [ row[0] for row in duck_conn.execute(query).fetchall()]
    
    elif role == "hr":
        query = "SELECT table_name FROM tables_metadata WHERE role = 'hr'"
        return [ row[0] for row in duck_conn.execute(query).fetchall()]
    
    elif role == "engineer":
        query = "SELECT table_name FROM tables_metadata WHERE role = 'engineer'"
        return [ row[0] for row in duck_conn.execute(query).fetchall()]
    
    else:
        query = """
        SELECT table_name FROM tables_metadata
        WHERE role = ? OR role = 'general' OR role = 'hr' OR role = 'engineer'
        """
        return [row[0] for row in duck_conn.execute(query, [role]).fetchall()]

def translate_nl_to_sql(question: str, allowed_tables: list[str]) -> str:

    sqlconn = get_sqlite_conn()
    sqlcur = sqlconn.cursor()

    # fetch headers from table
    sqlcur.execute(""" 
        SELECT filename, headers_Str FROM documents
        WHERE embedded = 1 AND headers_str IS NOT NULL
    """)
    rows = sqlcur.fetchall()

    print("Raw rows from DB:", rows)

    # creating schema from headers
    schemas =[]
    for filename, headers_Str in rows:

        try:
            table_name = Path(filename).stem.replace("-","_")
            print(table_name)

            cols = ",".join(headers_Str.split(","))
            print(cols)

            schemas.append(f"Table Name: {table_name}\nColumns: {cols}")

        except Exception as e:
            print(f"❌ Error while building schema for {filename}: {e}")

    print("Schemas: ",schemas)
    schema_block = "\n\n".join(schemas)
    print("Schema Block: ", schema_block)


    # Prompts for LLM
    prompt = f"""
        You are an expert SQLite query generation assistant.

        Your task is to convert natural language questions into SAFE and VALID SQLite SELECT queries only.

        Database Schema:
        {schema_block}

        Rules and Constraints:

        1. Generate ONLY a valid SQLite SELECT query [NEVER generate INSERT/UPDATE/DELETE/DROP/ALTER/CREATE]
        3. Use ONLY the tables and columns provided in the schema.
        4. Use exact table names and column names exactly as defined.
        5. Do NOT hallucinate columns or tables.
        6. If a requested field does not exist, infer the closest valid column name from the schema. 
           [example: if requested for 'employee name', consider closest alternatives like 'full-name', 'last-name'.
            if asked about 'position', consider 'title, 'role' or 'designation' if they exists]
        7. If multiple similar columns exist, choose the most semantically relevant one.
        8. If the question is ambiguous, generate the safest minimal query.
        9. Limit results to 100 rows unless user explicitly asks for more.
        10. Never mix aggregate functions with non-grouped columns improperly.
        11. Use aliases where readability improves clarity.
        12. Return ONLY raw SQL query text. Do NOT include - markdown/code fences, explanations, or comments.
        13. If query generation is impossible from provided schema, return exactly: INVALID_QUERY

        Natural Language Question: {question}

        SQL:
    """

    try:
        response = client.chat.completions.create(
            model="gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        print("LLM call successful.")

        response_txt = response.choices[0].message.content.strip()
        print("Raw SQL generated:", response_txt)

        return response_txt

    except Exception as e:
        print(f"❌ Error during LLM query generation: {e}")
        return "INVALID_QUERY"

FORBIDDEN = ["insert", "update", "delete", "drop", "alter", "create"]
def is_safe_query(sql:str) -> bool:
    sql_lower = sql.strip().lower().rstrip(";")
    return sql_lower.startswith("select") and all(word not in sql_lower for word in FORBIDDEN)

## Extract tables used in FROM and JOIN clauses
def extract_tables_from_sql(sql: str) -> list[str]:
    return re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', sql, flags=re.IGNORECASE)

# Flatten the list of tuples returned by regex to get a simple list of table names
def flatten_matches(matches: list[tuple]) -> list[str]:
    return [ item for tup in matches for item in tup if item]

# This function will contain the logic to parse the question, generate SQL query based on user role and execute it against the database.
def handle_sql_query(question:str, role:str, username:str, return_sql:bool=False) -> dict:
    
    try:
        allowed_tables = get_allowed_tables_for_role(role)
        
        # Validate tables exist for role
        if not allowed_tables:
            return {
                "answer": f"No data access available for role '{role}'. Please contact administrator.",
                "error": True
            }
        
        sql = translate_nl_to_sql(question, allowed_tables)
        print("Generated SQL:", sql)
        
        # Check for invalid query
        if sql.strip() == "INVALID_QUERY":
            return {
                "answer": "Unable to generate a valid SQL query for your question. Please rephrase your question with more specific terms.",
                "error": True
            }

        if not is_safe_query(sql):
            return {
                "answer": "Only SELECT queries are allowed.", 
                "error": True
            }

        raw_matches = extract_tables_from_sql(sql)
        referenced_tables = flatten_matches(raw_matches) 

        for table in referenced_tables:
            if table not in allowed_tables:
                return {
                    "answer": f"Access to table '{table}' is not allowed for your role.", 
                    "error": True
                }
        
        result = duck_conn.execute(sql).fetchall()
        columns = [desc[0] for desc in duck_conn.description]
        output = [ list(row) for row in result]

        markdown_table = tabulate.tabulate(output, headers=columns, tablefmt="github")
        response = {
            "answer": markdown_table if output else "Query executed successfully but returned no results.",
            "error": False
        }

        if return_sql:
            response["sql"] = sql

        return response
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ SQL Query Error: {error_msg}")
        return {
            "answer": f"Error executing query: {error_msg[:100]}", 
            "error": True
        }