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
                - action: str
                - status: str ("granted" or "denied")
        """
        for ev in events:
            self.evaluator.log_event(ev["user"], ev["action"], ev["status"])

        logs = self.evaluator.get_logs()
        metrics = self.evaluator.evaluate()

        result_df = pd.DataFrame(logs)
        result_file = self.raw_results_dir / f"audit_monitoring_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": metrics["total_logs"],
            "violations": metrics["violations"],
            "violation_rate": round(metrics["violation_rate"], 3),
        }

        summary_file = self.summary_dir / f"audit_monitoring_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
