# evaluator.py
from typing import Dict, List, Optional

class RBACSecurityEvaluator:
    def __init__(
        self,
        role_permissions: Dict[str, List[str]],
        min_permissions: Optional[Dict[str, List[str]]] = None,
    ):
        """
        role_permissions: dict mapping role -> list of allowed actions/resources.
        min_permissions:  optional dict mapping role -> *minimum* required actions.

        Example:
            role_permissions = {
                "C-Level": ["read", "create", "update", "delete"],
                "HR":      ["read", "update", "read_general"],
                "General": ["read_general"]
            }
            min_permissions = {
                "C-Level": ["read", "create", "update", "delete"],
                "HR":      ["read", "update", "read_general"],
                "General": ["read_general"]
            }
        """
        self.role_permissions = role_permissions
        self.min_permissions: Dict[str, List[str]] = (
            {k.casefold(): list(v) for k, v in min_permissions.items()}
            if min_permissions
            else {}
        )

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

        # Least-privilege:
        # 1.0  → granted ⊆ minimum
        # 0.0  → granted ⊃ minimum
        # 0.5  → no minimum baseline defined (neutral / unverifiable)
        min_key = role.casefold()
        if min_key in self.min_permissions:
            granted_set = set(allowed)
            minimum_set = set(self.min_permissions[min_key])
            least_privilege = 1.0 if granted_set <= minimum_set else 0.0
        else:
            least_privilege = 0.5 if role_match else 0.0

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
