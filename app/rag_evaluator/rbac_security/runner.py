import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple
from app.rag_evaluator.rbac_security.evaluator import RBACSecurityEvaluator


_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "c-level":   ["read", "create", "update", "delete"],
    "hr":        ["read", "update", "read_general"],
    "engineer":  ["read", "update", "read_general"],
    "finance":   ["read", "update", "read_general"],
    "marketing": ["read", "update", "read_general"],
    "general":   ["read_general"],
}

# Minimum-required action set per role
_ROLE_MIN_PERMISSIONS: Dict[str, List[str]] = {
    "c-level":   ["read", "create", "update", "delete"],
    "hr":        ["read", "update", "read_general"],
    "engineer":  ["read", "update", "read_general"],
    "finance":   ["read", "update", "read_general"],
    "marketing": ["read", "update", "read_general"],
    "general":   ["read_general"],
}

# High-privilege actions that all non-c-level roles must be denied.
_DENIED_ACTION = "create"
_PRIVILEGED_ROLES = {"c-level"}


class RbacSecurityRunner:
    """
    Runner for RBAC Security evaluation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = RBACSecurityEvaluator(
            role_permissions=_ROLE_PERMISSIONS,
            min_permissions=_ROLE_MIN_PERMISSIONS,
        )


    def _pick_allowed_action(self, role: str) -> str:
        """Return the first permitted action for the role."""
        return (_ROLE_PERMISSIONS.get(role, []) or ["__invalid_action__"])[0]

    def _pick_denied_action(self, role: str) -> str:
        """
        Return a high-privilege action the role must NOT be allowed to perform.
        """
        if role in _PRIVILEGED_ROLES:
            return "__out_of_policy_action__"
        return _DENIED_ACTION


    def run(self, qa_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        results = []

        for qa in qa_dataset:
            # Normalise role to lowercase — matches _ROLE_PERMISSIONS keys
            role = qa["role"].casefold()

            # --- Positive test: action the role IS permitted to perform ---
            allowed_action = self._pick_allowed_action(role)
            allowed_scores = self.evaluator.evaluate_query(role, allowed_action)
            results.append({
                "role": role,
                "source": qa["source"],
                "test_type": "allowed",
                "action_tested": allowed_action,
                "ground_truth": qa["answer"],
                **allowed_scores,
            })

            # --- Negative test: action the role must NOT be permitted to perform ---
            denied_action = self._pick_denied_action(role)
            denied_scores = self.evaluator.evaluate_query(role, denied_action)
            results.append({
                "role": role,
                "source": qa["source"],
                "test_type": "denied",
                "action_tested": denied_action,
                "ground_truth": qa["answer"],
                **denied_scores,
            })

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"rbac_security_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        # --- Summaries split by test_type for clarity ---
        allowed_df = result_df[result_df["test_type"] == "allowed"]
        denied_df  = result_df[result_df["test_type"] == "denied"]

        summary = {
            "samples": len(qa_dataset),
            "total_rows": len(result_df),
            # Positive-test metrics (should be 1.0 for all valid roles)
            "allowed_role_match_avg":       round(float(allowed_df["role_match"].mean()), 3),
            "allowed_compliance_score_avg": round(float(allowed_df["compliance_score"].mean()), 3),
            # Negative-test metrics (unauthorized_access should be 0.0 when correctly denied)
            "denied_unauthorized_access_avg": round(float(denied_df["unauthorized_access"].mean()), 3),
            # Cross-cutting metrics
            "least_privilege_avg": round(float(result_df["least_privilege"].mean()), 3),
            "auditability_avg":    round(float(result_df["auditability"].mean()), 3),
        }

        summary_file = self.summary_dir / f"rbac_security_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary