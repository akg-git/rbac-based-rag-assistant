import unittest
from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator
from app.rag_evaluator.text_to_sql.runner import TextToSQLRunner

class TestTextToSQLEvaluator(unittest.TestCase):
    def setUp(self):

        schema = {
            "users": ["id", "name", "email", "role_id"],
            "roles": ["id", "role_name", "permissions"],
            "documents": ["id", "title", "content", "created_at", "owner_role"],
            "orders": ["id", "user_id", "amount", "status", "created_at"],
            "audit_logs": ["id", "event_type", "role", "action", "timestamp", "status"]
        }

        self.evaluator = TextToSQLEvaluator(schema)

    def test_valid_sql(self):
        sql = "SELECT id, name, email FROM users;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertTrue(result["valid_schema"])
        self.assertEqual(result["errors"], [])

    def test_invalid_sql(self):
        sql = "SELEC id event_type FROM audit_logs;"
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])

    def test_invalid_schema(self):
        sql = "SELECT id, password FROM users;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])

    def test_invalid_column(self):
        sql = "SELECT titless FROM documents"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])

    def test_non_sql_statement(self):
        sql = "DROP DATABASE testdb"
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])

    def test_empty_query(self):
        sql = ""
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])

if __name__ == "__main__":
    unittest.main()
