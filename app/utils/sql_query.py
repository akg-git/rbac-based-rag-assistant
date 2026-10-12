import logging
import os
import uuid

import sqlparse
import tabulate
from groq import Groq
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import DML, Keyword, Newline, Whitespace
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from app.schemas.duckdb import get_duckdb_conn, get_duckdb_schema
from app.utils.audit_events import emit_audit_event
from app.utils.response_cache import sql_response_cache

from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger = logging.getLogger(__name__)


def get_allowed_tables_for_role(role: str, conn=None) -> list[str]:
    """Return physical tables authorized for a role."""
    normalized_role = role.casefold()
    owns_connection = conn is None
    conn = conn or get_duckdb_conn(read_only=True)
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
    except Exception as e:
        logger.error(f"[RBAC] Error retrieving allowed tables for role '{role}': {e}", exc_info=True)
        return []
    finally:
        if owns_connection:
            conn.close()


def _call_groq_with_backoff(model_name: str, prompt: str) -> str:
    """Invoke Groq with exponential-jitter backoff on rate-limit (429) errors."""

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential_jitter(initial=2, max=60, jitter=3),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _invoke() -> str:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    return _invoke()


def translate_nl_to_sql(question: str, allowed_tables: list[str], conn=None, error_feedback: str = "") -> str:
    """Generate DuckDB SQL using only catalog metadata for allowed tables."""
    owns_connection = conn is None
    conn = conn or get_duckdb_conn(read_only=True)
    try:
        schema = get_duckdb_schema(conn, allowed_tables)
        schema_block = "\n\n".join(
            f"Table Name: {table_name}\nColumns: {', '.join(columns)}"
            for table_name, columns in schema.items()
        )
        prompt = f"""You are an expert DuckDB query generation assistant.

Convert the natural language question into one safe DuckDB SELECT query.

Database Schema:
{schema_block}

Rules:
1. Generate one SELECT query only.
2. Use only the tables and columns in the schema.
3. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY,
   PRAGMA, ATTACH, INSTALL, LOAD, table functions, or subqueries.
4. Return only raw SQL without markdown (no ```sql tags), explanations, or comments. Example: SELECT * FROM table;
5. Return exactly INVALID_QUERY if generation is impossible.

Natural Language Question: {question}"""

        if error_feedback:
            prompt += f"\n\n{error_feedback}"

        prompt += "\n\nSQL:\n"

        model_name = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        raw_sql = _call_groq_with_backoff(model_name, prompt)

        if raw_sql.startswith("```sql"):
            raw_sql = raw_sql[6:].strip()
        elif raw_sql.startswith("```"):
            raw_sql = raw_sql[3:].strip()
        if raw_sql.endswith("```"):
            raw_sql = raw_sql[:-3].strip()

        return raw_sql.strip()
    except Exception as exc:
        logger.error("SQL generation failed: %s", type(exc).__name__)
        return "INVALID_QUERY"
    finally:
        if owns_connection:
            conn.close()


def generate_sql_with_retry(
    question: str,
    allowed_tables: list[str],
    conn=None,
    max_retries: int = 3,
) -> tuple[str, bool, list[str], str]:
    """
    Generate and validate SQL with self-correction retries.

    Returns:
        (sql, valid, referenced_tables, validation_error)
        - sql: final generated SQL (may be "INVALID_QUERY" or empty on total failure)
        - valid: True only if the SQL passed all validation checks
        - referenced_tables: tables parsed from the SQL
        - validation_error: last error message, empty string on success
    """
    from app.schemas.duckdb import get_duckdb_conn as _get_conn
    owns_connection = conn is None
    conn = conn or _get_conn()
    try:
        # ── Cache lookup ───────────────────────────────────────────────
        role_key = ",".join(sorted(allowed_tables))
        cached = sql_response_cache.get(question, role_key)
        if cached is not None:
            logger.info("[SQL] Cache hit — skipping LLM call.")
            cached_sql, cached_valid, cached_tables, cached_err = cached
            return cached_sql, cached_valid, cached_tables, cached_err

        sql = ""
        valid = False
        referenced_tables: list[str] = []
        validation_error = ""
        error_feedback = ""

        for attempt in range(max_retries):
            sql = translate_nl_to_sql(question, allowed_tables, conn, error_feedback)
            if not sql or sql.strip() == "INVALID_QUERY":
                break

            valid, referenced_tables, validation_error = validate_sql_query(
                sql, allowed_tables, conn
            )
            if valid:
                break

            error_feedback = (
                f"Previous SQL attempt:\n{sql}\n"
                f"Failed with error: {validation_error}\n"
                f"Please correct the SQL query to resolve this error."
            )
            logger.warning(
                "[SQL] Retry %d/%d — validation failed: %s", attempt + 1, max_retries, validation_error
            )

        # ── Cache store on success ─────────────────────────────────────
        if valid:
            sql_response_cache.set((sql, valid, referenced_tables, validation_error), question, role_key)
            logger.info("[SQL] Result cached for future identical queries.")

        return sql, valid, referenced_tables, validation_error
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
    except Exception as e:
        return False, referenced_tables, f"Database error: {str(e)}"
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


def _emit_sql_audit_event(
    *,
    username: str,
    role: str,
    action: str,
    resource: str,
    authorization_decision: str,
    result: str,
    outcome_status: str,
    request_id: str,
    correlation_id: str,
) -> None:
    """Persist a canonical authorization event for this SQL request."""
    emit_audit_event(
        user_id=username,
        role=role,
        action=action,
        resource=resource,
        authorization_decision=authorization_decision,
        result=result,
        outcome_status=outcome_status,
        request_id=request_id,
        correlation_id=correlation_id,
        query_mode="sql",
    )


def handle_sql_query(
    question: str,
    role: str,
    username: str,
    return_sql: bool = False,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Generate, authorize, validate, and execute one SQL query."""
    conn = get_duckdb_conn()
    request_id = request_id or str(uuid.uuid4())
    correlation_id = correlation_id or request_id
    resource = "sql_query"

    try:
        logger.info("[SQL] User=%s, Role=%s, Event=query_started", username, role)
        allowed_tables = get_allowed_tables_for_role(role, conn)
        if not allowed_tables:
            _emit_sql_audit_event(
                username=username,
                role=role,
                action="query",
                resource=resource,
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
                request_id=request_id,
                correlation_id=correlation_id,
            )
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

        MAX_RETRIES = 3
        sql = ""
        valid = False
        referenced_tables = []
        validation_error = ""
        error_feedback = ""
        
        for attempt in range(MAX_RETRIES):
            sql = translate_nl_to_sql(question, allowed_tables, conn, error_feedback)
            if sql.strip() == "INVALID_QUERY":
                break
                
            valid, referenced_tables, validation_error = validate_sql_query(
                sql,
                allowed_tables,
                conn,
            )
            
            if valid:
                break
                
            error_feedback = f"Previous SQL attempt:\n{sql}\nFailed with error: {validation_error}\nPlease correct the SQL query to resolve this error."
            
        if not sql or sql.strip() == "INVALID_QUERY":
            _emit_sql_audit_event(
                username=username,
                role=role,
                action="query",
                resource=resource,
                authorization_decision="denied",
                result="failure",
                outcome_status="failed",
                request_id=request_id,
                correlation_id=correlation_id,
            )
            return {
                "answer": "Unable to generate a valid SQL query for your question.",
                "error": True,
                "error_type": "validation",
            }

        if not valid:
            is_unauthorized_table = any(
                table.casefold() not in {allowed.casefold() for allowed in allowed_tables}
                for table in referenced_tables
            )
            _emit_sql_audit_event(
                username=username,
                role=role,
                action="query",
                resource=resource,
                authorization_decision="denied",
                result="failure",
                outcome_status="unauthorized" if is_unauthorized_table else "failed",
                request_id=request_id,
                correlation_id=correlation_id,
            )
            logger.warning(
                "[SQL] User=%s, Role=%s, Event=query_denied, Reason=sql_validation_failed",
                username,
                role,
            )
            return {
                "answer": validation_error,
                "error": True,
                "error_type": "authorization" if is_unauthorized_table else "validation",
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

        _emit_sql_audit_event(
            username=username,
            role=role,
            action="query",
            resource=resource,
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "[SQL] User=%s, Role=%s, Event=query_succeeded, Tables=%s",
            username,
            role,
            referenced_tables,
        )
        return response
    except Exception as exc:
        _emit_sql_audit_event(
            username=username,
            role=role,
            action="query",
            resource=resource,
            authorization_decision="denied",
            result="failure",
            outcome_status="failed",
            request_id=request_id,
            correlation_id=correlation_id,
        )
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
