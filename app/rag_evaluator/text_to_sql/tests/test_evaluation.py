import unittest
from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator
from app.rag_evaluator.text_to_sql.runner import TextToSQLRunner

class TestTextToSQLEvaluator(unittest.TestCase):
    def setUp(self):
        # Retrieve active schema dynamically from runner (no hardcoded dict duplication)
        runner = TextToSQLRunner()
        self.evaluator = runner.evaluator

    def test_valid_sql(self):
        sql = "SELECT full_name, email FROM hr_data;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertTrue(result["valid_schema"])
        self.assertTrue(result["is_read_only"])
        self.assertEqual(result["errors"], [])

    def test_wildcard_select(self):
        sql = "SELECT * FROM hr_data;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertTrue(result["valid_schema"])
        self.assertTrue(result["is_read_only"])

    def test_table_alias_and_aggregates(self):
        sql = "SELECT u.full_name, COUNT(u.employee_id) FROM hr_data u;"
        result = self.evaluator.evaluate(sql)
        self.assertTrue(result["valid_syntax"])
        self.assertTrue(result["valid_schema"])
        self.assertTrue(result["is_read_only"])

    def test_mutation_rejection(self):
        sql = "DELETE FROM hr_data WHERE employee_id=1;"
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])
        self.assertFalse(result["is_read_only"])
        self.assertTrue(any("mutation" in err.lower() for err in result["errors"]))

    def test_invalid_sql(self):
        sql = "SELEC full_name FROM hr_data;"
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])

    def test_invalid_schema(self):
        sql = "SELECT invalid_col FROM hr_data;"
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
        self.assertFalse(result["is_read_only"])

    def test_empty_query(self):
        sql = ""
        result = self.evaluator.evaluate(sql)
        self.assertFalse(result["valid_syntax"])
        self.assertFalse(result["valid_schema"])


class TestTextToSQLRunner(unittest.TestCase):
    def test_runner_dynamic_schema(self):
        runner = TextToSQLRunner()
        self.assertIn("hr_data", runner.evaluator.schema)

if __name__ == "__main__":
    unittest.main()
