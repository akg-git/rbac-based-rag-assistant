"""Pure metrics for evaluating authorization and audit event semantics."""

from collections import Counter
from typing import Any


class AuditMonitoringEvaluator:
    """Evaluate authorization decisions without treating expected denials as breaches."""

    def __init__(self, high_risk_actions: list[str] | None = None):
        self.high_risk_actions = {
            action.casefold() for action in (high_risk_actions or ["delete", "drop", "update"])
        }

    @staticmethod
    def _decision(event: dict[str, Any]) -> str:
        decision = event.get("authorization_decision", event.get("status", ""))
        normalized = str(decision).casefold()
        return "allowed" if normalized == "granted" else normalized

    @staticmethod
    def _outcome_status(event: dict[str, Any]) -> str:
        return str(event.get("outcome_status", event.get("status", ""))).casefold()

    @staticmethod
    def _user(event: dict[str, Any]) -> str:
        return str(event.get("user_id", event.get("user", "unknown")))

    def _is_high_risk_action(self, action: str) -> bool:
        normalized = str(action).casefold()
        return normalized in self.high_risk_actions or normalized.removesuffix("_data") in self.high_risk_actions

    def evaluate(self, audit_events: list[dict[str, Any]]) -> dict[str, float]:
        """Return authorization, policy, and suspicious-behavior metrics."""
        total = len(audit_events)
        allowed_actions = sum(
            1 for event in audit_events if self._decision(event) == "allowed"
        )
        denied_actions = sum(
            1 for event in audit_events if self._decision(event) == "denied"
        )
        violations = [
            event
            for event in audit_events
            if self._outcome_status(event) in {"unauthorized", "policy_breach"}
        ]
        high_risk_violations = sum(
            1
            for event in violations
            if self._is_high_risk_action(str(event.get("action", "")))
        )

        outcome_counts = Counter(self._user(event) for event in audit_events)
        failed_outcome_counts = Counter(
            self._user(event)
            for event in audit_events
            if self._outcome_status(event) == "failed"
        )
        suspicious_users = {
            user
            for user in outcome_counts
            if any(
                self._user(event) == user
                and self._outcome_status(event) in {"unauthorized", "policy_breach"}
                for event in audit_events
            )
            or failed_outcome_counts[user] > 1
        }

        violation_rate = len(violations) / total if total else 0.0
        compliance_rate = 1.0 - violation_rate
        return {
            "total_events": float(total),
            "allowed_actions": float(allowed_actions),
            "denied_actions": float(denied_actions),
            "violations": float(len(violations)),
            "violation_rate": round(violation_rate, 4),
            "compliance_rate": round(compliance_rate, 4),
            "high_risk_violations": float(high_risk_violations),
            "suspicious_users_count": float(len(suspicious_users)),
        }
