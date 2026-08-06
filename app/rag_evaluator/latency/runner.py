import os, json, pandas as pd, time
from pathlib import Path
from typing import List, Dict, Tuple, Callable

from app.rag_evaluator.latency.evaluator import LatencyEvaluator

class LatencyRunner:
    """
    Runner for Latency evaluation.
    Handles execution, persistence, and summary generation.
    """

    def __init__(self, report_dir: Path = Path("app/rag_evaluator/reports")):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"

        for folder in [self.raw_results_dir, self.summary_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        self.evaluator = LatencyEvaluator()

    def run(self, functions_to_test: List[Tuple[str, Callable, List, Dict]]) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            functions_to_test: list of tuples (name, func, args, kwargs)
        """
        results = []

        for name, func, args, kwargs in functions_to_test:
            scores = self.evaluator.measure_latency(func, *args, **kwargs)
            result_row = {
                "function": name,
                "latency_seconds": scores["latency_seconds"],
                "throughput_ops_per_sec": scores["throughput_ops_per_sec"],
                "result": scores["result"]
            }
            results.append(result_row)

        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"latency_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        summary = {
            "samples": len(result_df),
            "avg_latency": round(result_df["latency_seconds"].mean(), 6),
            "avg_throughput": round(result_df["throughput_ops_per_sec"].mean(), 6),
        }

        summary_file = self.summary_dir / f"latency_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
