import unittest
from app.rag_evaluator.rbac_security.evaluator import RBACSecurityEvaluator

class TestRBACSecurityEvaluator(unittest.TestCase):
    def setUp(self):
        self.role_permissions = {
            "C-Level": ["read", "create", "update", "delete"],
            "HR": ["read", "update", "read_general"],
            "Engineer": ["read", "update", "read_general"],
            "Finance": ["read", "update", "read_general"],
            "Marketing": ["read", "update", "read_general"],
            "General": ["read_general"]
        }
        self.evaluator = RBACSecurityEvaluator(self.role_permissions)

    # --- C-Level (Admin) ---
    def test_c_level_full_access(self):
        for action in ["read", "create", "update", "delete"]:
            result = self.evaluator.evaluate_query("C-Level", action)
            self.assertEqual(result["role_match"], 1.0)

    # --- HR Role ---
    def test_hr_allowed_actions(self):
        for action in ["read", "update", "read_general"]:
            result = self.evaluator.evaluate_query("HR", action)
            self.assertEqual(result["role_match"], 1.0)

    def test_hr_denied_create_delete(self):
        for action in ["create", "delete"]:
            result = self.evaluator.evaluate_query("HR", action)
            self.assertEqual(result["unauthorized_access"], 1.0)

    # --- Engineer Role ---
    def test_engineer_allowed_actions(self):
        for action in ["read", "update", "read_general"]:
            result = self.evaluator.evaluate_query("Engineer", action)
            self.assertEqual(result["role_match"], 1.0)

    def test_engineer_denied_create_delete(self):
        for action in ["create", "delete"]:
            result = self.evaluator.evaluate_query("Engineer", action)
            self.assertEqual(result["unauthorized_access"], 1.0)

    # --- Finance Role ---
    def test_finance_allowed_actions(self):
        for action in ["read", "update", "read_general"]:
            result = self.evaluator.evaluate_query("Finance", action)
            self.assertEqual(result["role_match"], 1.0)

    def test_finance_denied_create_delete(self):
        for action in ["create", "delete"]:
            result = self.evaluator.evaluate_query("Finance", action)
            self.assertEqual(result["unauthorized_access"], 1.0)

    # --- Marketing Role ---
    def test_marketing_allowed_actions(self):
        for action in ["read", "update", "read_general"]:
            result = self.evaluator.evaluate_query("Marketing", action)
            self.assertEqual(result["role_match"], 1.0)

    def test_marketing_denied_create_delete(self):
        for action in ["create", "delete"]:
            result = self.evaluator.evaluate_query("Marketing", action)
            self.assertEqual(result["unauthorized_access"], 1.0)

    # --- General Role ---
    def test_general_allowed_read_general(self):
        result = self.evaluator.evaluate_query("General", "read_general")
        self.assertEqual(result["role_match"], 1.0)

    def test_general_denied_other_actions(self):
        for action in ["read", "update", "create", "delete"]:
            result = self.evaluator.evaluate_query("General", action)
            self.assertEqual(result["unauthorized_access"], 1.0)

    # --- Edge Cases ---
    def test_unknown_role(self):
        result = self.evaluator.evaluate_query("Unknown", "read")
        self.assertEqual(result["role_match"], 0.0)

    def test_invalid_action(self):
        result = self.evaluator.evaluate_query("HR", "invalid_action")
        self.assertEqual(result["role_match"], 0.0)
        self.assertEqual(result["unauthorized_access"], 1.0)
        
if __name__ == "__main__":
    unittest.main()
