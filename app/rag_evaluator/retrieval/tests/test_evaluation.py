import unittest
from app.rag_evaluator.retrieval.evaluator import RetrievalEvaluator

class TestRetrievalEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = RetrievalEvaluator()
        self.retrieved = ["doc1", "doc2", "doc3", "doc4"]
        self.relevant = ["doc2", "doc4"]

    def test_empty_docs(self):
        result = self.evaluator.evaluate_retrieval("What is AI?", [], "Artificial Intelligence")
        for metric in ["context_precision", "context_recall",  "hit_rate", "mrr", "ndcg"]:
            self.assertEqual(result[metric], 0.0)

    def test_perfect_match(self):
        docs = ["Artificial Intelligence is the simulation of human intelligence."]
        result = self.evaluator.evaluate_retrieval("What is AI?", docs, "Artificial Intelligence")
        # All metrics should be floats in range
        for metric in ["context_precision", "context_recall",  "hit_rate", "mrr", "ndcg"]:
            self.assertIsInstance(result[metric], float)
            self.assertGreaterEqual(result[metric], 0.0)
            self.assertLessEqual(result[metric], 1.0)
        # context_recall and hit_rate should be 1.0
        self.assertEqual(result["context_recall"], 1.0)
        self.assertEqual(result["hit_rate"], 1.0)

    def test_no_match(self):
        docs = ["Machine learning is a subset of AI."]
        result = self.evaluator.evaluate_retrieval("What is AI?", docs, "Quantum Computing")
        for metric in ["context_precision", "context_recall",  "hit_rate", "mrr", "ndcg"]:
            self.assertEqual(result[metric], 0.0)

    def test_precision_at_k(self):
        score = self.evaluator._context_precision(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_recall_at_k(self):
        score = self.evaluator._context_recall(self.retrieved, self.relevant)
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

    def test_hit_rate(self):
        score = self.evaluator.hit_rate(self.retrieved, self.relevant)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_evaluate(self):
        results = self.evaluator.evaluate(self.retrieved, self.relevant)
        for metric in ["precision@k", "recall@k", "mrr", "ndcg@k",  "hit_rate"]:
            self.assertIn(metric, results)
            self.assertIsInstance(results[metric], float)
            self.assertGreaterEqual(results[metric], 0.0)
            self.assertLessEqual(results[metric], 1.0)

if __name__ == "__main__":
    unittest.main()
