import logging
import math
from typing import Dict, List, Sequence, Union

logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """
    Evaluates retrieval quality by comparing retrieved context
    against ground truth answers.
    """

    def __init__(self, k: int = 5):
        self.k = k

    @staticmethod
    def _normalize_docs(doc_ids: Union[str, Sequence[str], None]) -> List[str]:
        if doc_ids is None:
            return []
        if isinstance(doc_ids, str):
            return [doc_ids]
        return list(doc_ids)

    @staticmethod
    def _is_relevant(expected: str, retrieved: str) -> bool:
        expected_norm = expected.strip().lower()
        retrieved_norm = retrieved.strip().lower()
        return expected_norm in retrieved_norm or retrieved_norm in expected_norm

    @staticmethod
    def _context_precision(
        expected: List[str],
        retrieved: List[str]
    ) -> float:
        if not retrieved:
            return 0.0

        relevant_retrieved = sum(
            1 for doc in retrieved if any(
                RetrievalEvaluator._is_relevant(exp, doc) for exp in expected
            )
        )
        return relevant_retrieved / len(retrieved)

    @staticmethod
    def _context_recall(
        expected: List[str],
        retrieved: List[str]
    ) -> float:
        if not expected:
            return 0.0

        relevant_retrieved = sum(
            1 for exp in expected if any(
                RetrievalEvaluator._is_relevant(exp, doc) for doc in retrieved
            )
        )
        return relevant_retrieved / len(expected)

    @staticmethod
    def _hit_rate(
        expected: List[str],
        retrieved: List[str]
    ) -> float:
        return float(any(
            any(RetrievalEvaluator._is_relevant(exp, doc) for exp in expected)
            for doc in retrieved
        ))

    @staticmethod
    def _mrr(
        expected: List[str],
        retrieved: List[str]
    ) -> float:
        for rank, doc_id in enumerate(retrieved, start=1):
            if any(RetrievalEvaluator._is_relevant(exp, doc_id) for exp in expected):
                return 1.0 / rank

        return 0.0

    @staticmethod
    def _dcg(relevance_scores: List[float]) -> float:
        dcg = 0.0
        for idx, rel in enumerate(relevance_scores, start=1):
            dcg += rel / math.log2(idx + 1)
        return dcg

    @staticmethod
    def _ndcg(
        expected: List[str],
        retrieved: List[str]
    ) -> float:
        actual_relevance = [
            1.0 if any(RetrievalEvaluator._is_relevant(exp, doc) for exp in expected) else 0.0
            for doc in retrieved
        ]
        ideal_relevance = sorted(actual_relevance, reverse=True)

        dcg = RetrievalEvaluator._dcg(actual_relevance)
        idcg = RetrievalEvaluator._dcg(ideal_relevance)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def precision_at_k(self, retrieved_doc_ids: Union[str, Sequence[str]], relevant_doc_ids: Union[str, Sequence[str]]) -> float:
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        return float(self._context_precision(relevant, retrieved[: self.k]))

    def recall_at_k(self, retrieved_doc_ids: Union[str, Sequence[str]], relevant_doc_ids: Union[str, Sequence[str]]) -> float:
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        return float(self._context_recall(relevant, retrieved[: self.k]))

    def hit_rate(self, retrieved_doc_ids: Union[str, Sequence[str]], relevant_doc_ids: Union[str, Sequence[str]]) -> float:
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        return float(self._hit_rate(relevant, retrieved[: self.k]))

    def mrr(self, retrieved_doc_ids: Union[str, Sequence[str]], relevant_doc_ids: Union[str, Sequence[str]]) -> float:
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        return float(self._mrr(relevant, retrieved[: self.k]))

    def ndcg_at_k(self, retrieved_doc_ids: Union[str, Sequence[str]], relevant_doc_ids: Union[str, Sequence[str]]) -> float:
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        return float(self._ndcg(relevant, retrieved[: self.k]))

    def evaluate(
        self,
        retrieved_doc_ids: Union[str, Sequence[str]],
        relevant_doc_ids: Union[str, Sequence[str]]
    ) -> Dict[str, float]:
        """
        Public evaluator entrypoint used by the wider evaluation framework.
        """
        retrieved = self._normalize_docs(retrieved_doc_ids)
        relevant = self._normalize_docs(relevant_doc_ids)
        top_k_docs = retrieved[: self.k]

        return {
            "precision@k": round(self._context_precision(relevant, top_k_docs), 3),
            "recall@k": round(self._context_recall(relevant, top_k_docs), 3),
            "mrr": round(self._mrr(relevant, top_k_docs), 3),
            "ndcg@k": round(self._ndcg(relevant, top_k_docs), 3),
            "hit_rate": round(self._hit_rate(relevant, top_k_docs), 3),
        }

    def evaluate_retrieval(
        self,
        query: str,
        retrieved_doc_ids: Union[str, Sequence[str]],
        expected_doc_ids: Union[str, Sequence[str]]
    ) -> Dict[str, float]:
        """
        Backward-compatible alias for the retrieval pipeline.
        """
        retrieved = self._normalize_docs(retrieved_doc_ids)
        expected = self._normalize_docs(expected_doc_ids)
        top_k_docs = retrieved[: self.k]

        if not top_k_docs:
            return {
                "context_precision": 0.0,
                "context_recall": 0.0,
                "hit_rate": 0.0,
                "mrr": 0.0,
                "ndcg": 0.0
            }

        context_precision = self._context_precision(expected, top_k_docs)
        context_recall = self._context_recall(expected, top_k_docs)
        hit_rate = self._hit_rate(expected, top_k_docs)
        mrr = self._mrr(expected, top_k_docs)
        ndcg = self._ndcg(expected, top_k_docs)

        return {
            "context_precision": round(context_precision, 3),
            "context_recall": round(context_recall, 3),
            "hit_rate": round(hit_rate, 3),
            "mrr": round(mrr, 3),
            "ndcg": round(ndcg, 3)
        }
