# evaluator.py
from typing import List, Dict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class VectorDBEvaluator:
    def __init__(self):
        pass

    def embedding_quality(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> float:
        """
        Measure average cosine similarity between query and docs.
        """
        if doc_embeddings is None or len(doc_embeddings) == 0:
            return 0.0
    
        sims = cosine_similarity([query_embedding], doc_embeddings)[0]
        return float(np.mean(sims))

    def index_performance(self, retrieval_times: List[float]) -> Dict[str, float]:
        """
        Evaluate index performance based on retrieval times.
        """

        if not retrieval_times:
            return {"avg_retrieval_time": 0.0, "max_retrieval_time": 0.0, "min_retrieval_time": 0.0}

        return {
            "avg_retrieval_time": float(np.mean(retrieval_times)),
            "max_retrieval_time": float(np.max(retrieval_times)),
            "min_retrieval_time": float(np.min(retrieval_times)),
        }

    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray, retrieval_times: List[float]) -> Dict[str, float]:
        return {
            "embedding_quality": self.embedding_quality(query_embedding, doc_embeddings),
            **self.index_performance(retrieval_times),
        }
