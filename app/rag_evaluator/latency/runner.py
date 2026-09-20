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

    def run(self, functions_to_test: List[Tuple[str, Callable, List, Dict]], iterations: int = 5) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Args:
            functions_to_test: list of tuples (name, func, args, kwargs)
        """
        results = []
        all_measured_times: List[float] = []

        for item in functions_to_test:
            # Support (name, func, args, kwargs) or (name, func)
            name = item[0]
            func = item[1]
            args = item[2] if len(item) > 2 else []
            kwargs = item[3] if len(item) > 3 else {}

            sample_times = []
            for _ in range(iterations):
                start = time.perf_counter()
                func(*args, **kwargs)
                end = time.perf_counter()
                sample_times.append(end - start)

            all_measured_times.extend(sample_times)
            metrics = self.evaluator.evaluate(sample_times)

            result_row = {
                "function": name,
                "iterations": iterations,
                **metrics,
            }
            results.append(result_row)


        result_df = pd.DataFrame(results)
        result_file = self.raw_results_dir / f"latency_results_{self.timestamp}.csv"
        result_df.to_csv(result_file, index=False)

        # Global summary across all tested functions
        summary = self.evaluator.evaluate(all_measured_times)
        summary["total_benchmarks"] = len(result_df)

        summary_file = self.summary_dir / f"latency_summary_{self.timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        return result_df, summary
