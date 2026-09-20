# app/rag_evaluator/latency/evaluator.py
from typing import Dict, List, Union
import numpy as np


class LatencyEvaluator:
    """
    Pure metric computation module for latency and throughput benchmarks.
    Stateless and reusable.
    """

    def evaluate(self, latencies: Union[float, List[float]]) -> Dict[str, float]:
        """
        Input: Prepared latency duration (float) or list of durations in seconds.
        Output: Flat metrics dictionary.
        """
        if isinstance(latencies, (int, float)):
            latencies = [float(latencies)]

        if not latencies:
            return {
                "avg_latency": 0.0,
                "p50_latency": 0.0,
                "p95_latency": 0.0,
                "p99_latency": 0.0,
                "min_latency": 0.0,
                "max_latency": 0.0,
                "throughput_ops_per_sec": 0.0,
            }

        arr = np.array(latencies, dtype=float)
        avg_latency = float(np.mean(arr))
        throughput = float(1.0 / avg_latency) if avg_latency > 0 else 0.0

        return {
            "avg_latency": round(avg_latency, 6),
            "p50_latency": round(float(np.percentile(arr, 50)), 6),
            "p95_latency": round(float(np.percentile(arr, 95)), 6),
            "p99_latency": round(float(np.percentile(arr, 99)), 6),
            "min_latency": round(float(np.min(arr)), 6),
            "max_latency": round(float(np.max(arr)), 6),
            "throughput_ops_per_sec": round(throughput, 2),
        }

