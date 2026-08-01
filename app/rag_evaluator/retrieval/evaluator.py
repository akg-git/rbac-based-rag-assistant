# evaluator.py
from typing import List, Dict
import math
import numpy as np
# from sklearn.metrics import ndcg_score

@staticmethod
def _context_recall(
    expected: List[str],
    retrieved: List[str]
) -> float:

    if not expected:
        return 0.0

    relevant_retrieved = len(
        set(expected).intersection(set(retrieved))
    )

    return relevant_retrieved / len(expected)

@staticmethod
def _hit_rate(
    expected: List[str],
    retrieved: List[str]
) -> float:

    return float(
        any(doc in expected for doc in retrieved)
    )

@staticmethod
def _mrr(
    expected: List[str],
    retrieved: List[str]
) -> float:

    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in expected:
            return 1.0 / rank

    return 0.0

@staticmethod
def _dcg(relevance_scores: List[int]) -> float:
    dcg = 0.0

    for idx, rel in enumerate(relevance_scores):
        dcg += rel / math.log2(idx + 2)

    return dcg

def _ndcg(
    self,
    expected: List[str],
    retrieved: List[str]
) -> float:

    actual_relevance = [
        1 if doc in expected else 0
        for doc in retrieved
    ]

    ideal_relevance = sorted(
        actual_relevance,
        reverse=True
    )

    dcg = self._dcg(actual_relevance)
    idcg = self._dcg(ideal_relevance)

    if idcg == 0:
        return 0.0

    return dcg / idcg

class RetrievalEvaluator:

    """
    Pure retrieval evaluator.

    Inputs:
        expected_doc_ids  -> Ground truth relevant documents
        retrieved_doc_ids -> Documents returned by retriever

    Returns:
        Flat metrics dictionary.
    """
    
    def __init__(self, k: int = 5):
        self.k = k

    def evaluate(
        self,
        expected_doc_ids: List[str],
        retrieved_doc_ids: List[str]
    ) -> Dict[str, float]:

        top_k_docs = retrieved_doc_ids[: self.k]

        context_precision = self._context_precision(
            expected_doc_ids,
            top_k_docs
        )

        context_recall = self._context_recall(
            expected_doc_ids,
            top_k_docs
        )

        hit_rate = self._hit_rate(
            expected_doc_ids,
            top_k_docs
        )

        mrr = self._mrr(
            expected_doc_ids,
            top_k_docs
        )

        ndcg = self._ndcg(
            expected_doc_ids,
            top_k_docs
        )

        return {
            "context_precision": round(context_precision, 4),
            "context_recall": round(context_recall, 4),
            "hit_rate_at_k": round(hit_rate, 4),
            "mrr": round(mrr, 4),
            "ndcg_at_k": round(ndcg, 4)
        }
