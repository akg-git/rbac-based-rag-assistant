"""Metrics for evaluating a real Chroma-backed retrieval benchmark."""

from collections.abc import Sequence
from typing import Any

import numpy as np


class VectorDBEvaluator:
    """Calculate source-retrieval quality and index timing metrics."""

    def ranking_metrics(
        self,
        retrieved_sources: Sequence[str],
        expected_sources: Sequence[str],
        retrieval_times: Sequence[float],
        k: int = 5,
    ) -> dict[str, float]:
        """Evaluate Recall@K, MRR, and NDCG@K for ranked source results."""
        if k <= 0:
            raise ValueError("k must be greater than zero")

        retrieved_sources = list(retrieved_sources)
        expected_sources = set(expected_sources)
        relevant_count = len(expected_sources)

        relevant_hits = sum(source in expected_sources for source in retrieved_sources[:k])
        recall_at_k = relevant_hits / relevant_count if relevant_count else 0.0

        first_relevant_rank = next(
            (
                rank
                for rank, source in enumerate(retrieved_sources[:k], start=1)
                if source in expected_sources
            ),
            None,
        )
        reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank else 0.0

        dcg = sum(
            1.0 / np.log2(rank + 1)
            for rank, source in enumerate(retrieved_sources[:k], start=1)
            if source in expected_sources
        )
        ideal_dcg = sum(
            1.0 / np.log2(rank + 1)
            for rank in range(1, min(relevant_count, k) + 1)
        )
        ndcg_at_k = dcg / ideal_dcg if ideal_dcg else 0.0

        return {
            "recall_at_k": float(np.clip(recall_at_k, 0.0, 1.0)),
            "mrr": float(np.clip(reciprocal_rank, 0.0, 1.0)),
            "ndcg_at_k": float(np.clip(ndcg_at_k, 0.0, 1.0)),
            **self.index_performance(retrieval_times),
        }

    def index_performance(self, retrieval_times: Sequence[float]) -> dict[str, float]:
        """Return basic timing statistics for a retrieval run."""
        if not retrieval_times:
            return {
                "avg_retrieval_time": 0.0,
                "max_retrieval_time": 0.0,
                "min_retrieval_time": 0.0,
            }

        times = np.asarray(retrieval_times, dtype=float)
        return {
            "avg_retrieval_time": float(np.mean(times)),
            "max_retrieval_time": float(np.max(times)),
            "min_retrieval_time": float(np.min(times)),
        }

    def evaluate(
        self,
        retrieved_sources: Sequence[str],
        expected_sources: Sequence[str],
        retrieval_times: Sequence[float],
        k: int = 5,
    ) -> dict[str, float]:
        """Compatibility wrapper for the complete ranking evaluation."""
        return self.ranking_metrics(
            retrieved_sources,
            expected_sources,
            retrieval_times,
            k=k,
        )
