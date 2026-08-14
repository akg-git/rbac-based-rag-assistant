import unittest

import duckdb

from app.utils.sql_query import validate_sql_query


class TestSQLQuerySecurityIntegration(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect(":memory:")
        self.connection.execute(
            """
            CREATE TABLE SalesData (
                CustomerID INTEGER,
                Amount INTEGER
            )
            """
        )

    def tearDown(self):
        self.connection.close()

    def test_catalog_validation_accepts_case_insensitive_identifiers(self):
        valid, tables, error = validate_sql_query(
            "SELECT customerid, amount FROM salesdata",
            ["SalesData"],
            self.connection,
        )

        self.assertTrue(valid)
        self.assertEqual(tables, ["salesdata"])
        self.assertEqual(error, "")

    def test_rejects_unauthorized_table(self):
        valid, tables, error = validate_sql_query(
            "SELECT CustomerID FROM SecretData",
            ["SalesData"],
            self.connection,
        )

        self.assertFalse(valid)
        self.assertEqual(tables, ["SecretData"])
        self.assertIn("outside the user's permissions", error)

    def test_rejects_unauthorized_column(self):
        valid, tables, error = validate_sql_query(
            "SELECT Password FROM SalesData",
            ["SalesData"],
            self.connection,
        )

        self.assertFalse(valid)
        self.assertEqual(tables, ["SalesData"])
        self.assertIn("unknown table or column", error)

    def test_rejects_cte(self):
        valid, tables, error = validate_sql_query(
            "WITH data AS (SELECT CustomerID FROM SalesData) "
            "SELECT CustomerID FROM data",
            ["SalesData"],
            self.connection,
        )

        self.assertFalse(valid)
        self.assertEqual(tables, [])
        self.assertIn("Only SELECT statements", error)

    def test_rejects_multiple_statements(self):
        valid, tables, error = validate_sql_query(
            "SELECT CustomerID FROM SalesData; "
            "SELECT Amount FROM SalesData",
            ["SalesData"],
            self.connection,
        )

        self.assertFalse(valid)
        self.assertEqual(tables, [])
        self.assertIn("Exactly one SQL statement", error)

    def test_rejects_table_function(self):
        valid, tables, error = validate_sql_query(
            "SELECT * FROM read_csv_auto('sensitive.csv')",
            ["SalesData"],
            self.connection,
        )

        self.assertFalse(valid)
        self.assertEqual(tables, [])
        self.assertIn("table functions", error)


if __name__ == "__main__":
    unittest.main()
