import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple

from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator

class AuditMonitoringRunner:
    """
    Runner for Audit Monitoring evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = AuditMonitoringEvaluator()

    def run(self, events: List[Dict[str, str]]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            events: list of dicts with keys:
                - user: str
                - role: str
                - action: str
                - status: str ("granted" or "denied")
        """
        # 1. Invoke evaluator with prepared events
        summary_metrics = self.evaluator.evaluate(events)

        # 2. Add timestamp to events if missing for raw report
        prepared_rows = []
        for ev in events:
            row = dict(ev)
            if "timestamp" not in row:
                row["timestamp"] = self.timestamp
            prepared_rows.append(row)

        # 3. Save raw CSV
        result_df = pd.DataFrame(prepared_rows)
        result_file = self.raw_results_dir / f"audit_monitoring_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        # 4. Save summary JSON
        summary_file = self.summary_dir / f"audit_monitoring_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary_metrics, f, indent=4)

        return result_df, summary_metrics
