import unittest
import tempfile
import shutil
from pathlib import Path
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator
from app.rag_evaluator.audit_monitoring.runner import AuditMonitoringRunner


class TestAuditMonitoringEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = AuditMonitoringEvaluator()

    def test_empty_events(self):
        result = self.evaluator.evaluate([])
        self.assertEqual(result["total_events"], 0.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["violation_rate"], 0.0)
        self.assertEqual(result["compliance_rate"], 1.0)
        self.assertEqual(result["high_risk_violations"], 0.0)
        self.assertEqual(result["suspicious_users_count"], 0.0)

    def test_evaluate_basic(self):
        events = [
            {"user": "alice", "role": "C-Level", "action": "read", "status": "granted"},
            {"user": "bob", "role": "HR", "action": "delete", "status": "denied"},
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["total_events"], 2.0)
        self.assertEqual(result["violations"], 1.0)
        self.assertAlmostEqual(result["violation_rate"], 0.5)
        self.assertAlmostEqual(result["compliance_rate"], 0.5)
        self.assertEqual(result["high_risk_violations"], 1.0)
        self.assertEqual(result["suspicious_users_count"], 0.0)

    def test_high_risk_violations(self):
        events = [
            {"user": "mallory", "role": "guest", "action": "delete", "status": "denied"},
            {"user": "mallory", "role": "guest", "action": "drop", "status": "denied"},
            {"user": "alice", "role": "admin", "action": "delete", "status": "granted"},
        ]
        result = self.evaluator.evaluate(events)

        self.assertEqual(result["total_events"], 3.0)
        self.assertEqual(result["violations"], 2.0)
        # 2 denied attempts are high risk ("delete", "drop")
        self.assertEqual(result["high_risk_violations"], 2.0)
        # mallory has 2 denials -> suspicious user
        self.assertEqual(result["suspicious_users_count"], 1.0)

    def test_custom_high_risk_actions(self):
        custom_evaluator = AuditMonitoringEvaluator(high_risk_actions=["export_all", "nuke"])
        events = [
            {"user": "dave", "role": "analyst", "action": "export_all", "status": "denied"},
            {"user": "dave", "role": "analyst", "action": "delete", "status": "denied"},
        ]
        result = custom_evaluator.evaluate(events)
        self.assertEqual(result["high_risk_violations"], 1.0)

    def test_case_insensitivity(self):
        events = [
            {"user": "alice", "role": "HR", "action": "READ", "status": "GRANTED"},
            {"user": "bob", "role": "General", "action": "DELETE", "status": "DENIED"},
        ]
        result = self.evaluator.evaluate(events)
        self.assertEqual(result["violations"], 1.0)
        self.assertEqual(result["high_risk_violations"], 1.0)

    def test_runner_execution(self):
        temp_dir = tempfile.mkdtemp()
        try:
            runner = AuditMonitoringRunner(report_dir=Path(temp_dir))
            events = [
                {"user": "alice", "role": "C-Level", "action": "read", "status": "granted"},
                {"user": "bob", "role": "HR", "action": "delete", "status": "denied"},
            ]
            df, summary = runner.run(events)

            self.assertEqual(len(df), 2)
            self.assertIn("timestamp", df.columns)
            self.assertEqual(summary["total_events"], 2.0)
            self.assertEqual(summary["violations"], 1.0)

            raw_files = list((Path(temp_dir) / "raw_results").glob("*.csv"))
            summary_files = list((Path(temp_dir) / "summaries").glob("*.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(len(summary_files), 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
