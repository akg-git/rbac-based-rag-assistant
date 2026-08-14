import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple

from app.rag_evaluator.rbac_security.evaluator import RBACSecurityEvaluator

class RbacSecurityRunner:
    """
    Runner for RBAC Security evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.role_permissions = {
            "C-Level": ["read", "create", "update", "delete"],
            "HR": ["read", "update", "read_general"],
            "Engineer": ["read", "update", "read_general"],
            "Finance": ["read", "update", "read_general"],
            "Marketing": ["read", "update", "read_general"],
            "General": ["read_general"]
        }

        self.evaluator = RBACSecurityEvaluator(self.role_permissions)

    def run(self, qa_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        results = []

        for qa in qa_dataset:
            role = qa["role"]
            query_action = (self.role_permissions.get(role, []) or ["__invalid_action__"])[0]

            scores = self.evaluator.evaluate_query(role, query_action)

            result_row = {
                "role": role,
                "source": qa["source"],
                "ground_truth": qa["answer"],
                **scores
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"rbac_security_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "role_match_avg": round(result_df["role_match"].mean(), 3),
            "unauthorized_access_avg": round(result_df["unauthorized_access"].mean(), 3),
            "least_privilege_avg": round(result_df["least_privilege"].mean(), 3),
            "auditability_avg": round(result_df["auditability"].mean(), 3),
        }

        summary_file = self.summary_dir / f"rbac_security_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary