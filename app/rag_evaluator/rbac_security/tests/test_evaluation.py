import unittest
from app.rag_evaluator.rbac_security.evaluator import RBACSecurityEvaluator

class TestRBACSecurityEvaluator(unittest.TestCase):
    def setUp(self):
        self.role_permissions = {
            "admin": ["read_all", "write_all", "delete"],
            "user": ["read_own"],
            "guest": ["read_public"]
        }
        self.evaluator = RBACSecurityEvaluator(self.role_permissions)

    def test_check_access(self):
        self.assertTrue(self.evaluator.check_access("admin", "read_all"))
        self.assertFalse(self.evaluator.check_access("user", "delete"))

    def test_evaluate_query_compliant(self):
        result = self.evaluator.evaluate_query("user", ["read_own"])
        self.assertEqual(result["compliance_score"], 1.0)
        self.assertEqual(result["violations"], 0)

    def test_evaluate_query_violation(self):
        result = self.evaluator.evaluate_query("guest", ["read_public", "delete"])
        self.assertLess(result["compliance_score"], 1.0)
        self.assertEqual(result["violations"], 1)

    def test_evaluate_session(self):
        session = [["read_own"], ["delete"], ["read_own", "read_all"]]
        result = self.evaluator.evaluate_session("user", session)
        self.assertIsInstance(result["avg_compliance"], float)
        self.assertGreaterEqual(result["avg_compliance"], 0.0)
        self.assertLessEqual(result["avg_compliance"], 1.0)
        self.assertGreaterEqual(result["total_violations"], 0)

if __name__ == "__main__":
    unittest.main()
