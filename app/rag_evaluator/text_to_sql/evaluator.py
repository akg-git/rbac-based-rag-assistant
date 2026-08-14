# evaluator.py
import re
from typing import Dict, Any, List
try:
    import sqlparse
    from sqlparse.sql import IdentifierList, Identifier
except ImportError:  # pragma: no cover - exercised when optional dep is missing
    sqlparse = None

class TextToSQLEvaluator:
    def __init__(self, schema: Dict[str, List[str]]):
        """
        schema: dict mapping table -> list of columns
        Example: {"users": ["id", "name", "email"], "orders": ["id", "user_id", "amount"]}
        """
        self.schema = schema

    def _extract_columns(self, parsed_stmt) -> List[str]:
        """Helper to extract column names from a parsed SQL statement."""
        columns = []
        for token in parsed_stmt.tokens:
            if token.value.upper() == "FROM":
                break
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    if str(identifier):
                        columns.append(str(identifier).lower())
            elif isinstance(token, Identifier):
                if token.get_name():
                    columns.append(token.get_name().lower())
        return columns

    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL syntax and schema compliance.
        """
        result = {"valid_syntax": False, "valid_schema": False, "errors": []}

        sql_upper = sql.strip().upper()
        if not sql_upper.startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            return result

        parsed = None
        if sqlparse is not None:
            try:
                parsed = sqlparse.parse(sql)
            except Exception as exc:
                result["errors"].append(str(exc))
                return result

        result["valid_syntax"] = True

        if parsed:
            stmt = parsed[0]
            selected_cols = self._extract_columns(stmt)

            tokens = [t.value.lower() for t in parsed[0].tokens if not t.is_whitespace]
            if not selected_cols:
                selected_cols = [tok for tok in tokens if tok not in ["select", "from", ",", ";"]]
            table_name = None
            for table, cols in self.schema.items():
                if table.lower() in tokens:
                    table_name = table
                    break
            if table_name is not None:
                schema_cols = [c.lower() for c in self.schema[table_name]]
                result["valid_schema"] = bool(selected_cols) and all(col in schema_cols for col in selected_cols)
            return result

        table_match = re.search(r"\bfrom\s+([a-zA-Z_][\w]*)", sql, re.IGNORECASE)
        column_match = re.search(r"\bselect\s+(.*?)\s+from", sql, re.IGNORECASE | re.DOTALL)
        if table_match:
            table_name = table_match.group(1).lower()
            schema_cols = [c.lower() for c in self.schema.get(table_name, [])]
            if column_match:
                selected_cols = [col.strip().lower() for col in column_match.group(1).split(",") if col.strip()]
            else:
                selected_cols = []
            result["valid_schema"] = bool(selected_cols) and all(col in schema_cols for col in selected_cols)

        return result

    def evaluate(self, sql: str) -> Dict[str, Any]:
        """Public entry point for evaluation (fixes AttributeError)."""
        return self.validate_sql(sql)