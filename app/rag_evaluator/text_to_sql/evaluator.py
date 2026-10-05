import re
from typing import Dict, Any, List, Set

class TextToSQLEvaluator:
    MUTATION_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"}

    def __init__(self, schema: Dict[str, List[str]] = None):
        """
        schema: dict mapping table -> list of columns
        Example: {"users": ["id", "name", "email"], "hr_data": ["employee_id", "salary"]}
        """
        self.schema = {k.casefold(): [c.casefold() for c in v] for k, v in (schema or {}).items()}

    def set_schema(self, schema: Dict[str, List[str]]):
        self.schema = {k.casefold(): [c.casefold() for c in v] for k, v in schema.items()}

    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL syntax, read-only safety (no mutations), and schema compliance.
        """
        result = {
            "valid_syntax": False,
            "valid_schema": False,
            "is_read_only": True,
            "errors": []
        }

        if not sql or not isinstance(sql, str) or not sql.strip():
            result["errors"].append("Empty SQL query string.")
            return result

        clean_sql = sql.strip().rstrip(";")
        sql_upper = clean_sql.upper()

        # Check for mutation operations
        words = set(re.findall(r"\b[A-Z_]+\b", sql_upper))
        detected_mutations = words.intersection(self.MUTATION_KEYWORDS)
        if detected_mutations or not sql_upper.startswith("SELECT"):
            result["is_read_only"] = False
            result["valid_syntax"] = False
            result["errors"].append(
                f"Unauthorized mutation or non-SELECT statement detected: {', '.join(sorted(detected_mutations)) if detected_mutations else 'non-SELECT'}"
            )
            return result

        result["valid_syntax"] = True

        # Extract table names referenced in query (FROM <table>, JOIN <table>)
        table_matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)", clean_sql, re.IGNORECASE)
        referenced_tables = [t.casefold() for t in table_matches]

        if not referenced_tables:
            result["errors"].append("No table specified in FROM/JOIN clause.")
            return result

        # Verify referenced tables exist in schema
        if self.schema:
            invalid_tables = [t for t in referenced_tables if t not in self.schema]
            if invalid_tables:
                result["errors"].append(f"Referenced unknown table(s): {', '.join(invalid_tables)}")
                return result

        # Extract column references from SELECT clause
        select_match = re.search(r"\bSELECT\s+(.*?)\s+\bFROM\b", clean_sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            result["errors"].append("Could not parse SELECT clause.")
            return result

        select_clause = select_match.group(1).strip()

        # If SELECT *, valid as long as referenced tables exist in schema
        if select_clause == "*":
            result["valid_schema"] = True
            return result

        # Extract column names from expressions like u.name, COUNT(id), SUM(o.amount) AS total
        col_exprs = [c.strip() for c in select_clause.split(",") if c.strip()]
        extracted_cols = []
        sql_func_keywords = {
            "count", "avg", "sum", "min", "max", "distinct", "coalesce", "cast",
            "nullif", "case", "when", "then", "else", "end", "as", "over", "partition", "by"
        }

        for expr in col_exprs:
            # Strip AS alias
            expr_no_alias = re.split(r"\bAS\b", expr, flags=re.IGNORECASE)[0].strip()
            # Find identifiers (e.g. u.name -> name, employee_id -> employee_id)
            tokens = re.findall(r"\b(?:[a-zA-Z_][\w]*\.)?([a-zA-Z_][\w]*)\b", expr_no_alias)
            cols = [t.casefold() for t in tokens if t.casefold() not in sql_func_keywords and not t.isdigit()]
            extracted_cols.extend(cols)

        if not extracted_cols:
            # e.g., SELECT COUNT(*) FROM table -> valid schema if table exists
            result["valid_schema"] = True
            return result

        # Check extracted columns against schema for the referenced tables
        if self.schema:
            allowed_cols: Set[str] = set()
            for t in referenced_tables:
                allowed_cols.update(self.schema.get(t, []))

            invalid_cols = [c for c in extracted_cols if c not in allowed_cols]
            if invalid_cols:
                result["errors"].append(f"Column(s) not in schema: {', '.join(invalid_cols)}")
                result["valid_schema"] = False
            else:
                result["valid_schema"] = True
        else:
            result["valid_schema"] = True

        return result

    def evaluate(self, sql: str) -> Dict[str, Any]:
        """Public entry point for evaluation."""
        return self.validate_sql(sql)