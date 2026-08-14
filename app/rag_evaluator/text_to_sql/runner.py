import json
import logging
import pandas as pd
import time
from pathlib import Path
from typing import List, Dict, Tuple

from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator
from app.utils.sql_query import translate_nl_to_sql

logger = logging.getLogger(__name__)


class TextToSQLRunner:
    """
    Runner for Text-to-SQL evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = Path(report_dir) if report_dir is not None else Path("app/rag_evaluator/reports")
        self.raw_results_dir = self.report_dir / "raw_results"
        self.summary_dir = self.report_dir / "summaries"
        self.logs_dir = self.report_dir / "logs"

        for folder in [self.raw_results_dir, self.summary_dir, self.logs_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        schema = {
            "users": ["id", "name", "email", "role_id"],
            "roles": ["id", "role_name", "permissions"],
            "documents": ["id", "title", "content", "created_at", "owner_role"],
            "orders": ["id", "user_id", "amount", "status", "created_at"],
            "audit_logs": ["id", "event_type", "role", "action", "timestamp", "status"]
        }

        self.evaluator = TextToSQLEvaluator(schema)

    def run(self, sql_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            sql_dataset: list of dicts with keys:
                - query: str (SQL string)
                - source: str (origin of query)
        """
        results = []

        for item in sql_dataset:

            sql = translate_nl_to_sql(item["question"], item["role"]) 

            if sql is None:
                logger.warning("Skipping text-to-SQL row without query/question key: %s", item)
                continue

            scores = self.evaluator.evaluate(sql)

            result_row = {
                "query": sql,
                "source": item.get("source","unknown"),
                "valid_syntax": scores["valid_syntax"],
                "valid_schema": scores["valid_schema"],
                "errors": ";".join(scores["errors"]) if scores["errors"] else "",
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"text_to_sql_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "syntax_valid_rate": round(result_df["valid_syntax"].mean(), 3),
            "schema_valid_rate": round(result_df["valid_schema"].mean(), 3),
            "error_count": sum(1 for e in result_df["errors"] if e),
        }

        summary_file = self.summary_dir / f"text_to_sql_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
