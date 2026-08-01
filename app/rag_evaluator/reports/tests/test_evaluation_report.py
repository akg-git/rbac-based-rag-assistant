import unittest
import numpy as np
from app.rag_evaluator.reports.evaluation_report import EvaluationReport

class TestEvaluationReport(unittest.TestCase):
    def setUp(self):
        schema = {"users": ["id", "name", "email"]}
        role_permissions = {"admin": ["read_all", "write_all"], "user": ["read_own"]}
        self.reporter = EvaluationReport(schema, role_permissions)

    def test_generate_report(self):
        query = "What is AI?"
        context = "Artificial Intelligence basics"
        answer = "AI is machine learning"
        retrieved_docs = ["doc1", "doc2"]
        relevant_docs = ["doc2"]
        role = "user"
        query_actions = ["read_own"]
        query_embedding = np.array([0.1, 0.2, 0.3])
        doc_embeddings = np.array([[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]])
        retrieval_times = [0.05, 0.07]
        sql = "SELECT id, name, email FROM users;"

        report = self.reporter.generate_report(
            query, context, answer,
            retrieved_docs, relevant_docs,
            role, query_actions,
            query_embedding, doc_embeddings, retrieval_times,
            sql
        )

        self.assertIn("answer_quality", report)
        self.assertIn("retrieval", report)
        self.assertIn("rbac_security", report)
        self.assertIn("latency", report)
        self.assertIn("vector_db", report)
        self.assertIn("text_to_sql", report)
        self.assertIn("audit_monitoring", report)

    def test_generate_report_with_shorter_retrieval_list(self):
        report = self.reporter.generate_report(
            "What is AI?",
            "Artificial Intelligence basics",
            "AI is machine learning",
            ["doc1"],
            ["doc1"],
            "user",
            ["read_own"],
            np.array([0.1, 0.2, 0.3]),
            np.array([[0.1, 0.2, 0.3]]),
            [0.05],
            "SELECT id FROM users;",
        )

        self.assertEqual(report["retrieval"]["precision@k"], 1.0)
        self.assertEqual(report["retrieval"]["ndcg@k"], 1.0)

if __name__ == "__main__":
    unittest.main()
