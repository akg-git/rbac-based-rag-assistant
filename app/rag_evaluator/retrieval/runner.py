import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple

from app.rag_evaluator.retrieval.evaluator import RetrievalEvaluator

class RetrievalRunner:
    """
    Runner for Retrieval evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = RetrievalEvaluator()

    def run(self, qa_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        results = []

        for qa in qa_dataset:
            query = qa["question"]
            ground_truth = qa["answer"]
            retrieved_docs = qa.get("retrieved_docs", [])
            relevant_docs = qa.get("relevant_docs", [ground_truth])

            if not retrieved_docs:
                print(f"Warning: missing retrieved_docs for question: {query}")

            scores = self.evaluator.evaluate_retrieval(
                query,
                retrieved_docs,
                relevant_docs,
            )

            result_row = {
                "question": query,
                "role": qa["role"],
                "source": qa["source"],
                "ground_truth": ground_truth,
                **scores
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"retrieval_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "precision_avg": round(result_df["context_precision"].mean(), 3),
            "recall_avg": round(result_df["context_recall"].mean(), 3),
            "hit_rate_avg": round(result_df["hit_rate"].mean(), 3),
            "mrr_avg": round(result_df["mrr"].mean(), 3),
            "ndcg_avg": round(result_df["ndcg"].mean(), 3)
        }

        summary_file = self.summary_dir / f"retrieval_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
