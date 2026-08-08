import unittest
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator

class TestAuditMonitoringEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = AuditMonitoringEvaluator()

    def test_log_event_and_evaluate(self):
        self.evaluator.log_event("alice", "read_data", "granted")
        self.evaluator.log_event("bob", "delete_data", "denied")
        result = self.evaluator.evaluate_security()

        self.assertEqual(result["total_logs"], 2.0)
        self.assertEqual(result["violations"], 1.0)
        self.assertAlmostEqual(result["violation_rate"], 0.5)

    def test_empty_logs(self):
        result = self.evaluator.evaluate_security()
        self.assertEqual(result["total_logs"], 0.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["violation_rate"], 0.0)

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
