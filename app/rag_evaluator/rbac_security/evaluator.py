# evaluator.py
from typing import List, Dict

class RBACSecurityEvaluator:
    def __init__(self, role_permissions: Dict[str, List[str]]):
        """
        role_permissions: dict mapping role -> list of allowed actions/resources
        Example: {"admin": ["read_all", "write_all"], "user": ["read_own"]}
        """
        self.role_permissions = role_permissions

    def check_access(self, role: str, action: str) -> bool:
        """Check if a given role is allowed to perform an action."""
        allowed = self.role_permissions.get(role, [])
        return action in allowed

    def evaluate_query(self, role: str, query_actions: List[str]) -> Dict[str, float]:
        """
        Evaluate if all actions in a query are permitted for the role.
        Returns metrics on compliance.
        """
        allowed = self.role_permissions.get(role, [])
        permitted = sum(1 for act in query_actions if act in allowed)
        denied = len(query_actions) - permitted

        return {
            "compliance_score": permitted / len(query_actions) if query_actions else 1.0,
            "violations": denied,
            "permitted": permitted,
            "total_actions": len(query_actions),
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
