import json
import logging
import pandas as pd
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator
from app.utils.sql_query import generate_sql_with_retry, get_allowed_tables_for_role

logger = logging.getLogger(__name__)


class TextToSQLRunner:
    """
    Runner for Text-to-SQL evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports"), schema: Optional[Dict[str, List[str]]] = None):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = Path(report_dir) if report_dir is not None else Path("app/rag_evaluator/reports")
        self.raw_results_dir = self.report_dir / "raw_results"
        self.summary_dir = self.report_dir / "summaries"
        self.logs_dir = self.report_dir / "logs"

        for folder in [self.raw_results_dir, self.summary_dir, self.logs_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        if schema is None:
            schema = self._load_duckdb_schema()

        self.evaluator = TextToSQLEvaluator(schema)

    def _load_duckdb_schema(self) -> Dict[str, List[str]]:
        """Dynamically fetch schema from active DuckDB catalog. Fallback only if database is empty."""
        try:
            from app.schemas.duckdb import get_duckdb_conn, get_duckdb_schema
            conn = get_duckdb_conn(read_only=True)
            db_schema = get_duckdb_schema(conn)
            conn.close()
            if db_schema:
                return db_schema
        except Exception as exc:
            logger.warning(f"Could not load dynamic DuckDB schema: {exc}")

        # Fallback ONLY when DuckDB database has no tables loaded
        return {
            "hr_data": ["employee_id", "full_name", "role", "department", "email", "location", "salary"],
        }

    def run(self, sql_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            sql_dataset: list of dicts with keys:
                - question (or query): str
                - role: str
                - source: str (optional)
        """
        results = []

        for item in sql_dataset:
            question = item.get("question", item.get("query", ""))
            role = item.get("role", "general")
            source = str(item.get("source", "")).strip().lower()

            if not question:
                logger.warning("Skipping text-to-SQL row without question/query key: %s", item)
                continue

            allowed_tables = get_allowed_tables_for_role(role)

            # Skip unstructured documents (.md, .txt) that have no mapped database tables
            if not allowed_tables and (source.endswith(".md") or source.endswith(".txt")):
                logger.info("Skipping unstructured document source '%s' (role '%s') from SQL evaluation", source, role)
                continue

            # If a role has no database tables at all, skip non-SQL evaluations
            if not allowed_tables:
                logger.info("Skipping text-to-SQL evaluation for role '%s' with no allowed tables: %s", role, question)
                continue

            sql, valid, _, _ = generate_sql_with_retry(question, allowed_tables)

            if not sql or sql.strip() == "INVALID_QUERY":
                logger.warning("Failed text-to-SQL generation for question: %s", question)
                scores = {
                    "valid_syntax": False,
                    "valid_schema": False,
                    "is_read_only": True,
                    "errors": ["Failed to generate valid SQL query after retries"]
                }
                sql = "INVALID_QUERY"
            else:
                scores = self.evaluator.evaluate(sql)

            result_row = {
                "question": question,
                "role": role,
                "query": sql,
                "source": item.get("source", "unknown"),
                "valid_syntax": scores["valid_syntax"],
                "valid_schema": scores["valid_schema"],
                "is_read_only": scores.get("is_read_only", True),
                "errors": "; ".join(scores["errors"]) if scores["errors"] else "",
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"text_to_sql_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "syntax_valid_rate": round(result_df["valid_syntax"].mean(), 3) if not result_df.empty else 0.0,
            "schema_valid_rate": round(result_df["valid_schema"].mean(), 3) if not result_df.empty else 0.0,
            "read_only_rate": round(result_df["is_read_only"].mean(), 3) if not result_df.empty else 1.0,
            "error_count": sum(1 for e in result_df["errors"] if e) if not result_df.empty else 0,
        }

        summary_file = self.summary_dir / f"text_to_sql_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
