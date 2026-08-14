# evaluator.py
import time
from typing import Dict, Any, List

class AuditMonitoringEvaluator:
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def log_event(self, user: str,  role: str, action: str, status: str) -> None:
        """
        Log security or system events.
        """
        self.logs.append({
            "timestamp": time.time(),
            "user": user,
            "role": role,
            "action": action,
            "status": status
        })

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.logs

    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate logs for suspicious activity.
        """
        violations = [log for log in self.logs if log["status"] == "denied"]
        return {
            "total_logs": len(self.logs),
            "violations": len(violations),
            "violation_rate": len(violations) / len(self.logs) if self.logs else 0.0
        }
