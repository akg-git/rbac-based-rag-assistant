import shutil
import tempfile
import unittest
from pathlib import Path
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator
from app.rag_evaluator.audit_monitoring.runner import AuditMonitoringRunner


class TestAuditMonitoringEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = AuditMonitoringEvaluator()

    def event(self, **overrides):
        event = {
            "event_id": "event-1",
            "timestamp": "2026-10-06T00:00:00Z",
            "user_id": "alice",
            "role": "employee",
            "request_id": "request-1",
            "action": "read_data",
            "resource": "employee_records",
            "authorization_decision": "allowed",
            "result": "success",
            "outcome_status": "authorized",
            "correlation_id": "correlation-1",
            "event_hash": "hash",
        }
        event.update(overrides)
        return event

    def test_empty_events(self):
        result = self.evaluator.evaluate([])
        self.assertEqual(result["total_events"], 0.0)
        self.assertEqual(result["allowed_actions"], 0.0)
        self.assertEqual(result["denied_actions"], 0.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["violation_rate"], 0.0)
        self.assertEqual(result["compliance_rate"], 1.0)
        self.assertEqual(result["high_risk_violations"], 0.0)
        self.assertEqual(result["suspicious_users_count"], 0.0)

    def test_expected_denied_action_is_not_a_violation(self):
        events = [
            self.event(
                event_id="event-1",
                user_id="bob",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
            ),
            self.event(
                event_id="event-2",
                user_id="bob",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
                action="delete_data",
            ),
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["total_events"], 2.0)
        self.assertEqual(result["allowed_actions"], 0.0)
        self.assertEqual(result["denied_actions"], 2.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["violation_rate"], 0.0)
        self.assertEqual(result["compliance_rate"], 1.0)
        self.assertEqual(result["high_risk_violations"], 0.0)
        self.assertEqual(result["suspicious_users_count"], 0.0)

    def test_unauthorized_outcome_is_a_violation(self):
        events = [
            self.event(
                event_id="event-1",
                user_id="mallory",
                action="delete_data",
                authorization_decision="allowed",
                result="success",
                outcome_status="unauthorized",
            ),
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["violations"], 1.0)
        self.assertEqual(result["violation_rate"], 1.0)
        self.assertEqual(result["compliance_rate"], 0.0)
        self.assertEqual(result["high_risk_violations"], 1.0)
        self.assertEqual(result["suspicious_users_count"], 1.0)

    def test_failed_outcomes_are_not_security_violations(self):
        events = [
            self.event(
                event_id="event-1",
                user_id="alice",
                result="failure",
                outcome_status="failed",
            ),
            self.event(
                event_id="event-2",
                user_id="alice",
                result="failure",
                outcome_status="failed",
            ),
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["high_risk_violations"], 0.0)
        self.assertEqual(result["suspicious_users_count"], 1.0)

    def test_custom_high_risk_actions_only_count_unauthorized_events(self):
        evaluator = AuditMonitoringEvaluator(high_risk_actions=["export_all", "nuke"])
        events = [
            self.event(
                event_id="event-1",
                user_id="dave",
                action="export_all",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
            ),
            self.event(
                event_id="event-2",
                user_id="dave",
                action="export_all",
                authorization_decision="allowed",
                result="success",
                outcome_status="unauthorized",
            ),
        ]
        result = evaluator.evaluate(events)
        self.assertEqual(result["high_risk_violations"], 1.0)

    def test_legacy_status_fields_remain_compatible(self):
        events = [
            {
                "user": "alice",
                "role": "HR",
                "action": "read",
                "status": "granted",
            },
            {
                "user": "bob",
                "role": "General",
                "action": "delete",
                "status": "denied",
            },
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["allowed_actions"], 1.0)
        self.assertEqual(result["denied_actions"], 1.0)
        self.assertEqual(result["violations"], 0.0)

    def test_runner_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = AuditMonitoringRunner(report_dir=Path(temp_dir))
            events = [
                self.event(
                    event_id="event-1",
                    authorization_decision="allowed",
                    outcome_status="authorized",
                ),
                self.event(
                    event_id="event-2",
                    user_id="bob",
                    authorization_decision="denied",
                    outcome_status="denied",
                ),
            ]
            df, summary = runner.run(events)

            self.assertEqual(len(df), 2)
            self.assertIn("timestamp", df.columns)
            self.assertEqual(summary["total_events"], 2.0)
            self.assertEqual(summary["allowed_actions"], 1.0)
            self.assertEqual(summary["denied_actions"], 1.0)
            self.assertEqual(summary["violations"], 0.0)

            raw_files = list((Path(temp_dir) / "raw_results").glob("*.csv"))
            summary_files = list((Path(temp_dir) / "summaries").glob("*.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(len(summary_files), 1)


if __name__ == "__main__":
    unittest.main()
