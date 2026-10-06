import re
from typing import Dict, Any, List

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

        # Extract table names and aliases referenced in the query.
        table_pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)"
            r"(?:\s+(?:AS\s+)?([a-zA-Z_][\w]*))?"
            r"(?=\s+(?:WHERE|GROUP|HAVING|ORDER|LIMIT|JOIN|ON)\b|\s*;|\s*$)",
            re.IGNORECASE,
        )
        table_matches = table_pattern.findall(clean_sql)
        referenced_tables = [table.casefold() for table, _ in table_matches]
        table_aliases = {
            alias.casefold(): table.casefold()
            for table, alias in table_matches
            if alias
        }
        table_aliases.update({table.casefold(): table.casefold() for table, _ in table_matches})

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

        # Extract column names and their optional table qualifiers.
        col_exprs = [c.strip() for c in select_clause.split(",") if c.strip()]
        extracted_cols = []
        sql_func_keywords = {
            "count", "avg", "sum", "min", "max", "distinct", "coalesce", "cast",
            "nullif", "case", "when", "then", "else", "end", "as", "over", "partition",
            "by", "where", "group", "having", "order", "limit", "from", "join", "on",
            "select", "as", "is", "not", "null", "and", "or"
        }

        for expr in col_exprs:
            expr_no_alias = re.split(r"\bAS\b", expr, flags=re.IGNORECASE)[0].strip()
            identifier_matches = re.findall(
                r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b|\b([a-zA-Z_][\w]*)\b",
                expr_no_alias,
                re.IGNORECASE,
            )
            for qualifier, column, unqualified_column in identifier_matches:
                if qualifier:
                    extracted_cols.append((qualifier.casefold(), column.casefold()))
                elif unqualified_column.casefold() not in sql_func_keywords:
                    extracted_cols.append((None, unqualified_column.casefold()))

        if not extracted_cols:
            # e.g., SELECT COUNT(*) FROM table -> valid schema if table exists
            result["valid_schema"] = True
            return result

        if not self.schema:
            result["valid_schema"] = True
            return result

        invalid_columns = []
        allowed_columns_by_table = {
            table: set(self.schema.get(table, []))
            for table in referenced_tables
        }

        for qualifier, column in extracted_cols:
            if qualifier:
                table = table_aliases.get(qualifier)
                if table is None:
                    invalid_columns.append(f"Unknown table alias '{qualifier}' for column '{column}'")
                    continue
                if column not in allowed_columns_by_table[table]:
                    invalid_columns.append(f"Column '{qualifier}.{column}' does not exist in table '{table}'")
                continue

            matching_tables = [
                table for table, columns in allowed_columns_by_table.items()
                if column in columns
            ]
            if not matching_tables:
                invalid_columns.append(f"Column '{column}' does not exist in referenced tables")
            elif len(matching_tables) > 1:
                invalid_columns.append(
                    f"Column '{column}' is ambiguous across tables: {', '.join(sorted(matching_tables))}"
                )

        if invalid_columns:
            result["errors"].append("; ".join(invalid_columns))
            result["valid_schema"] = False
        else:
            result["valid_schema"] = True

        return result

    def evaluate(self, sql: str) -> Dict[str, Any]:
        """Public entry point for evaluation."""
        return self.validate_sql(sql)