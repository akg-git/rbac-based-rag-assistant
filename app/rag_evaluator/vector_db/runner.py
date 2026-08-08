import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

from app.rag_evaluator.vector_db.evaluator import VectorDBEvaluator

class VectorDBRunner:
    """
    Runner for Vector DB evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = VectorDBEvaluator()

    def run(self, queries: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            queries: list of dicts with keys:
                - query_embedding: np.ndarray
                - doc_embeddings: np.ndarray
                - retrieval_times: List[float]
                - query: str
        """
        results = []

        for q in queries:
            scores = self.evaluator.evaluate(
                q["query_embedding"], q["doc_embeddings"], q["retrieval_times"]
            )
            result_row = {
                "query": q["query"],
                "embedding_quality": scores["embedding_quality"],
                "avg_retrieval_time": scores["avg_retrieval_time"],
                "max_retrieval_time": scores["max_retrieval_time"],
                "min_retrieval_time": scores["min_retrieval_time"],
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"vector_db_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "embedding_quality_avg": round(result_df["embedding_quality"].mean(), 3),
            "avg_retrieval_time_avg": round(result_df["avg_retrieval_time"].mean(), 6),
            "max_retrieval_time_avg": round(result_df["max_retrieval_time"].mean(), 6),
            "min_retrieval_time_avg": round(result_df["min_retrieval_time"].mean(), 6),
        }

        summary_file = self.summary_dir / f"vector_db_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
