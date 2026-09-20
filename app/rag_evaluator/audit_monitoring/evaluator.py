# app/rag_evaluator/audit_monitoring/evaluator.py
from typing import Dict, List, Any


class AuditMonitoringEvaluator:
    """
    Pure metric computation module for audit and security monitoring logs.
    Stateless and reusable.
    """

    def __init__(self, high_risk_actions: List[str] = None):
        self.high_risk_actions = set(high_risk_actions or ["delete", "drop", "update", "delete_data", "write_data"])

    def evaluate(self, audit_events: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Input: Prepared list of audit log event dicts.
        Output: Flat metrics dictionary.
        """
        total = len(audit_events)
        if total == 0:
            return {
                "total_events": 0.0,
                "violations": 0.0,
                "violation_rate": 0.0,
                "compliance_rate": 1.0,
                "high_risk_violations": 0.0,
                "suspicious_users_count": 0.0,
            }

        violations = [e for e in audit_events if str(e.get("status", "")).lower() == "denied"]
        num_violations = len(violations)

        # High-risk denied attempts
        high_risk_denials = sum(
            1 for e in violations if str(e.get("action", "")).lower() in self.high_risk_actions
        )

        # Flag repeated violation users (users with > 1 denial in batch)
        user_denial_counts: Dict[str, int] = {}
        for e in violations:
            user = e.get("user", "unknown")
            user_denial_counts[user] = user_denial_counts.get(user, 0) + 1
        
        suspicious_users = sum(1 for count in user_denial_counts.values() if count > 1)

        violation_rate = num_violations / total
        compliance_rate = 1.0 - violation_rate

        return {
            "total_events": float(total),
            "violations": float(num_violations),
            "violation_rate": round(violation_rate, 4),
            "compliance_rate": round(compliance_rate, 4),
            "high_risk_violations": float(high_risk_denials),
            "suspicious_users_count": float(suspicious_users),
        }
