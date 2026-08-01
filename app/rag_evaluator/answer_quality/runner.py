import os
import time
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple

from app.rag_evaluator.answer_quality.evaluator import AnswerQualityEvaluator


class AnswerQualityRunner:
    """
    Runner for Answer Quality evaluation.
    Responsibilities:
    - Prepare evaluator inputs
    - Invoke AnswerQualityEvaluator
    - Collect raw results
    - Generate summaries
    - Save CSV and JSON outputs
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = AnswerQualityEvaluator()

    def run(self, qa_dataset: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Run Answer Quality evaluation on a QA dataset.

        Args:
            qa_dataset: List of QA pairs with keys:
                        - question
                        - answer
                        - role
                        - source

        Returns:
            result_df: DataFrame of raw results
            summary: Dict of aggregated metrics
        """
        results = []

        for qa in qa_dataset:
            query = qa["question"]
            ground_truth = qa["answer"]

            scores = self.evaluator.evaluate_answer(
                query=query,
                context=qa.get("context", ""),  # context may be optional
                generated_answer=qa.get("generated_answer", ground_truth),
                reference_answer=ground_truth
            )

            result_row = {
                "question": query,
                "role": qa["role"],
                "source": qa["source"],
                "generated_answer": qa.get("generated_answer", ground_truth),
                "ground_truth": ground_truth,
                **scores
            }
            results.append(result_row)

        # Save raw results
        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"answer_quality_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        # Generate summary
        summary = {
            "samples": len(result_df),
            "faithfulness_avg": round(result_df["faithfulness"].mean(), 3),
            "relevance_avg": round(result_df["relevance"].mean(), 3),
            "clarity_avg": round(result_df["clarity"].mean(), 3),
            "completeness_avg": round(result_df["completeness"].mean(), 3),
            "embedding_similarity_avg": round(result_df["embedding_similarity"].mean(), 3),
        }

        summary_file = self.summary_dir / f"answer_quality_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
