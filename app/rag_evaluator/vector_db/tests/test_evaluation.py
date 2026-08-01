import unittest
import numpy as np
from app.rag_evaluator.vector_db.evaluator import VectorDBEvaluator

class TestVectorDBEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = VectorDBEvaluator()
        self.query_embedding = np.array([0.1, 0.2, 0.3])
        self.doc_embeddings = np.array([[0.1, 0.2, 0.3],
                                        [0.2, 0.1, 0.4],
                                        [0.9, 0.8, 0.7]])
        self.retrieval_times = [0.05, 0.07, 0.06]

    def test_embedding_quality(self):
        score = self.evaluator.embedding_quality(self.query_embedding, self.doc_embeddings)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, -1.0)
        self.assertLessEqual(score, 1.0)

    def test_index_performance(self):
        result = self.evaluator.index_performance(self.retrieval_times)
        self.assertIn("avg_retrieval_time", result)
        self.assertIn("max_retrieval_time", result)
        self.assertIn("min_retrieval_time", result)

    def test_evaluate(self):
        result = self.evaluator.evaluate(self.query_embedding, self.doc_embeddings, self.retrieval_times)
        self.assertIn("embedding_quality", result)
        self.assertIn("avg_retrieval_time", result)

if __name__ == "__main__":
    unittest.main()
