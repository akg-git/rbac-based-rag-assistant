import unittest
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator

class TestAuditMonitoringEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = AuditMonitoringEvaluator()

        self.events = [
            {"user": "alice", "role": "C-Level", "action": "read", "status": "granted"},
            {"user": "bob", "role": "HR", "action": "delete", "status": "denied"},
        ]

        for ev in self.events:
            self.evaluator.log_event(ev["user"], ev["role"], ev["action"], ev["status"])

    def test_log_event_and_evaluate(self):
        self.evaluator = AuditMonitoringEvaluator()
        self.evaluator.log_event("alice", "C-Level", "read", "granted")
        self.evaluator.log_event("bob", "HR", "delete", "denied")
        result = self.evaluator.evaluate()

        self.assertEqual(result["total_logs"], 2)
        self.assertEqual(result["violations"], 1)
        self.assertAlmostEqual(result["violation_rate"], 0.5)

    def test_empty_logs(self):
        self.evaluator = AuditMonitoringEvaluator()
        result = self.evaluator.evaluate()
        self.assertEqual(result["total_logs"], 0)
        self.assertEqual(result["violations"], 0)
        self.assertEqual(result["violation_rate"], 0.0)

if __name__ == "__main__":
    unittest.main()
