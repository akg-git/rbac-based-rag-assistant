import unittest
from app.rag_evaluator.retrieval.evaluator import RetrievalEvaluator

class TestRetrievalEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = RetrievalEvaluator(k=3)
        self.retrieved = ["doc1", "doc2", "doc3", "doc4"]
        self.relevant = ["doc2", "doc4"]

    def test_precision_at_k(self):
        score = self.evaluator.precision_at_k(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_recall_at_k(self):
        score = self.evaluator.recall_at_k(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_mrr(self):
        score = self.evaluator.mrr(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_ndcg_at_k(self):
        score = self.evaluator.ndcg_at_k(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_evaluate(self):
        results = self.evaluator.evaluate(self.retrieved, self.relevant)
        for metric in ["precision@k", "recall@k", "mrr", "ndcg@k"]:
            self.assertIn(metric, results)
            self.assertIsInstance(results[metric], float)
            self.assertGreaterEqual(results[metric], 0.0)
            self.assertLessEqual(results[metric], 1.0)

if __name__ == "__main__":
    unittest.main()
