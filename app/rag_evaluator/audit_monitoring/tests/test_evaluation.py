import unittest
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator

class TestAuditMonitoringEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = AuditMonitoringEvaluator()

    def test_log_event_and_retrieve(self):
        self.evaluator.log_event("alice", "read_data", "granted")
        logs = self.evaluator.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user"], "alice")

    def test_evaluate_security(self):
        self.evaluator.log_event("bob", "delete_data", "denied")
        self.evaluator.log_event("alice", "read_data", "granted")
        result = self.evaluator.evaluate_security()
        self.assertEqual(result["total_logs"], 2)
        self.assertEqual(result["violations"], 1)
        self.assertGreaterEqual(result["violation_rate"], 0.0)
        self.assertLessEqual(result["violation_rate"], 1.0)

if __name__ == "__main__":
    unittest.main()
