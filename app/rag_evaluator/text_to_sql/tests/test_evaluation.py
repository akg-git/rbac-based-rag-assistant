import unittest
from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator

class TestTextToSQLEvaluator(unittest.TestCase):
    def setUp(self):
        schema = {"users": ["id", "name", "email"]}
        self.evaluator = TextToSQLEvaluator(schema)

    def test_valid_sql(self):
        sql = "SELECT id, name, email FROM users;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertTrue(result["valid_schema"])
        self.assertEqual(result["errors"], [])

    def test_invalid_sql(self):
        sql = "SELEC id name FROM users;"
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])

    def test_invalid_schema(self):
        sql = "SELECT id, password FROM users;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])

    def test_invalid_column(self):
        sql = "SELECT age FROM users"
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
