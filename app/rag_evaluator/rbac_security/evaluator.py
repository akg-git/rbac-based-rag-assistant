# evaluator.py
from typing import Dict, List

class RBACSecurityEvaluator:
    def __init__(self, role_permissions: Dict[str, List[str]]):
        """
        role_permissions: dict mapping role -> list of allowed actions/resources
        Example: {  "C-Level": ["read", "create", "update", "delete"],
                    "HR": ["read", "update", "read_general"],
                    "General": ["read_general"]     }
        """
        self.role_permissions = role_permissions

    def check_access(self, role: str, action: str) -> bool:
        """Check if a given role is allowed to perform an action."""
        allowed = self.role_permissions.get(role, [])
        return action in allowed

    def evaluate_query(
        self,
        role: str,
        query_action: List[str],
    ) -> Dict[str, float]:
        """
        Evaluate whether a role is allowed to perform a query action.
        Returns metrics on compliance.
        """
        query_actions = [query_action] if isinstance(query_action, str) else query_action
        allowed = self.role_permissions.get(role, [])
        permitted = sum(1 for act in query_actions if act in allowed)
        denied = len(query_actions) - permitted

        role_match = 1.0 if permitted > 0 else 0.0
        least_privilege = 1.0 if role_match and len(allowed) == 1 else 0.5 if role_match else 0.0
        auditability = 1.0 if query_actions else 0.0
        unauthorized_access = 1 if denied else 0

        return {
            "compliance_score": float(permitted / len(query_actions)) if query_actions else 1.0,
            "violations": float(denied),
            "unauthorized_access": float(unauthorized_access),
            "permitted": float(permitted),
            "total_actions": float(len(query_actions)),
            "role_match": role_match,
            "least_privilege": least_privilege,
            "auditability": auditability
        }

    def evaluate_session(self, role: str, session_queries: List[List[str]]) -> Dict[str, float]:
        """
        Evaluate multiple queries in a session.
        Returns average compliance and total violations.
        """
        results = [self.evaluate_query(role, q) for q in session_queries]
        avg_compliance = sum(r["compliance_score"] for r in results) / len(results) if results else 1.0
        total_violations = sum(r["violations"] for r in results)

        return {
            "avg_compliance": avg_compliance,
            "total_violations": total_violations,
            "queries_evaluated": len(results),
        }
