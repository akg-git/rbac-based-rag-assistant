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

    def test_compliance_full_access(self):
        result = self.evaluator.evaluate_query("admin", ["read_all"])
        self.assertEqual(result["compliance_score"], 1.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["permitted"], 1.0)
        self.assertEqual(result["total_actions"], 1.0)

    def test_compliance_partial_access(self):
        result = self.evaluator.evaluate_query("user", ["read_own", "write_all"])
        # user can only do "read_own"
        self.assertEqual(result["compliance_score"], 0.5)
        self.assertEqual(result["violations"], 1.0)
        self.assertEqual(result["permitted"], 1.0)
        self.assertEqual(result["total_actions"], 2.0)

    def test_compliance_no_access(self):
        result = self.evaluator.evaluate_query("user", ["write_all"])
        self.assertEqual(result["compliance_score"], 0.0)
        self.assertEqual(result["violations"], 1.0)
        self.assertEqual(result["permitted"], 0.0)
        self.assertEqual(result["total_actions"], 1.0)

    def test_empty_query_actions(self):
        result = self.evaluator.evaluate_query("admin", [])
        # No actions requested → compliance_score defaults to 1.0
        self.assertEqual(result["compliance_score"], 1.0)
        self.assertEqual(result["violations"], 0.0)
        self.assertEqual(result["permitted"], 0.0)
        self.assertEqual(result["total_actions"], 0.0)

    def test_evaluate_session(self):
        session = [["read_own"], ["delete"], ["read_own", "read_all"]]
        result = self.evaluator.evaluate_session("user", session)
        self.assertIsInstance(result["avg_compliance"], float)
        self.assertGreaterEqual(result["avg_compliance"], 0.0)
        self.assertLessEqual(result["avg_compliance"], 1.0)
        self.assertGreaterEqual(result["total_violations"], 0)

if __name__ == "__main__":
    unittest.main()
