import logging
import os

import sqlparse
import tabulate
from groq import Groq
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import DML, Keyword, Newline, Whitespace

from app.schemas.duckdb import get_duckdb_conn, get_duckdb_schema


client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger = logging.getLogger(__name__)


def get_allowed_tables_for_role(role: str) -> list[str]:
    """Return physical tables authorized for a role."""
    normalized_role = role.casefold()
    conn = get_duckdb_conn(read_only=True)
    try:
        if normalized_role == "c-level":
            query = """
                SELECT table_name
                FROM tables_metadata
                WHERE table_name <> 'tables_metadata'
            """
            params = []
        else:
            query = """
                SELECT table_name
                FROM tables_metadata
                WHERE table_name <> 'tables_metadata'
                  AND (lower(role) = ? OR lower(role) = 'general')
            """
            params = [normalized_role]
        return [row[0] for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def translate_nl_to_sql(question: str, allowed_tables: list[str], conn=None) -> str:
    """Generate DuckDB SQL using only catalog metadata for allowed tables."""
    owns_connection = conn is None
    conn = conn or get_duckdb_conn(read_only=True)
    try:
        schema = get_duckdb_schema(conn, allowed_tables)
        schema_block = "\n\n".join(
            f"Table Name: {table_name}\nColumns: {', '.join(columns)}"
            for table_name, columns in schema.items()
        )
        prompt = f"""
        You are an expert DuckDB query generation assistant.

        Convert the natural language question into one safe DuckDB SELECT query.

        Database Schema:
        {schema_block}

        Rules:
        1. Generate one SELECT query only.
        2. Use only the tables and columns in the schema.
        3. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY,
           PRAGMA, ATTACH, INSTALL, LOAD, table functions, or subqueries.
        4. Return only raw SQL without markdown, explanations, or comments.
        5. Return exactly INVALID_QUERY if generation is impossible.

        Natural Language Question: {question}

        SQL:
        """
        response = client.chat.completions.create(
            model="gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("SQL generation failed: %s", type(exc).__name__)
        return "INVALID_QUERY"
    finally:
        if owns_connection:
            conn.close()


def _meaningful_tokens(statement):
    return [
        token
        for token in statement.tokens
        if token.ttype not in (Whitespace, Newline)
    ]


def _extract_table_names(statement) -> list[str]:
    """Extract direct table identifiers from FROM and JOIN clauses."""
    tables = []
    tokens = _meaningful_tokens(statement)
    for index, token in enumerate(tokens):
        if token.ttype is not Keyword or token.normalized not in {"FROM", "JOIN"}:
            continue
        if index + 1 >= len(tokens):
            raise ValueError("SQL table source is missing.")

        source = tokens[index + 1]
        if isinstance(source, (Function, Parenthesis)):
            raise ValueError("SQL table functions and subqueries are not allowed.")

        identifiers = (
            source.get_identifiers()
            if isinstance(source, IdentifierList)
            else [source]
        )
        for identifier in identifiers:
            if not isinstance(identifier, Identifier) or not identifier.get_real_name():
                raise ValueError("Only direct table identifiers are allowed.")
            tables.append(identifier.get_real_name())

    if not tables:
        raise ValueError("SQL query must reference a table.")
    return tables


def validate_sql_query(sql: str, allowed_tables: list[str], conn=None) -> tuple[bool, list[str], str]:
    """Validate one SELECT and bind table/column names through DuckDB."""
    statements = sqlparse.parse(sql)
    if len(statements) != 1:
        return False, [], "Exactly one SQL statement is required."

    statement = statements[0]
    tokens = _meaningful_tokens(statement)
    if not tokens or tokens[0].ttype is not DML or tokens[0].normalized != "SELECT":
        return False, [], "Only SELECT statements are allowed."

    unsupported = {
        "WITH", "UNION", "INTERSECT", "EXCEPT", "COPY", "PRAGMA",
        "ATTACH", "INSTALL", "LOAD",
    }
    if any(
        token.normalized in unsupported
        for token in tokens
        if token.ttype in (Keyword, DML)
    ):
        return False, [], "This SQL construct is not allowed."

    try:
        referenced_tables = _extract_table_names(statement)
    except ValueError as exc:
        return False, [], str(exc)

    allowed = {str(table).casefold() for table in allowed_tables}
    if any(table.casefold() not in allowed for table in referenced_tables):
        return False, referenced_tables, "Query references a table outside the user's permissions."

    owns_connection = conn is None
    conn = conn or get_duckdb_conn(read_only=True)
    try:
        conn.execute(f"EXPLAIN {sql}")
    except Exception:
        return False, referenced_tables, "Query references an unknown table or column."
    finally:
        if owns_connection:
            conn.close()

    return True, referenced_tables, ""


def is_safe_query(sql: str) -> bool:
    """Compatibility helper using parser-based validation."""
    try:
        statement = sqlparse.parse(sql)[0]
        tables = _extract_table_names(statement)
        valid, _, _ = validate_sql_query(sql, tables)
        return valid
    except (IndexError, ValueError, sqlparse.exceptions.SQLParseError):
        return False


def handle_sql_query(question: str, role: str, username: str, return_sql: bool = False) -> dict:
    """Generate, authorize, validate, and execute one SQL query."""
    conn = get_duckdb_conn()
    try:
        logger.info("[SQL] User=%s, Role=%s, Event=query_started", username, role)
        allowed_tables = get_allowed_tables_for_role(role)
        if not allowed_tables:
            logger.warning(
                "[SQL] User=%s, Role=%s, Event=query_denied, Reason=no_allowed_tables",
                username,
                role,
            )
            return {
                "answer": f"No data access available for role '{role}'. Please contact administrator.",
                "error": True,
                "error_type": "authorization",
            }

        sql = translate_nl_to_sql(question, allowed_tables, conn)
        if sql.strip() == "INVALID_QUERY":
            return {
                "answer": "Unable to generate a valid SQL query for your question.",
                "error": True,
            }

        valid, referenced_tables, validation_error = validate_sql_query(
            sql,
            allowed_tables,
            conn,
        )
        if not valid:
            logger.warning(
                "[SQL] User=%s, Role=%s, Event=query_denied, Reason=sql_validation_failed",
                username,
                role,
            )
            error_type = (
                "authorization"
                if any(
                    table.casefold() not in {allowed.casefold() for allowed in allowed_tables}
                    for table in referenced_tables
                )
                else "validation"
            )
            return {
                "answer": validation_error,
                "error": True,
                "error_type": error_type,
            }

        result = conn.execute(sql).fetchall()
        columns = [description[0] for description in conn.description]
        output = [list(row) for row in result]
        response = {
            "answer": tabulate.tabulate(output, headers=columns, tablefmt="github")
            if output
            else "Query executed successfully but returned no results.",
            "error": False,
        }
        if return_sql:
            response["sql"] = sql

        logger.info(
            "[SQL] User=%s, Role=%s, Event=query_succeeded, Tables=%s",
            username,
            role,
            referenced_tables,
        )
        return response
    except Exception as exc:
        logger.error(
            "[SQL] User=%s, Role=%s, Event=query_failed, ErrorType=%s",
            username,
            role,
            type(exc).__name__,
            exc_info=True,
        )
        return {"answer": "Error executing query.", "error": True, "error_type": "execution"}
    finally:
        conn.close()
