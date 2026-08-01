# evaluator.py
import time
from typing import Callable, Dict

class LatencyEvaluator:
    def __init__(self):
        pass

    def measure_latency(self, func: Callable, *args, **kwargs) -> Dict[str, float]:
        """
        Measure latency of a function call.
        Returns response time and throughput metrics.
        """
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()

        latency = end - start
        throughput = 1.0 / latency if latency > 0 else float("inf")

        return {
            "latency_seconds": latency,
            "throughput_ops_per_sec": throughput,
            "result": result,
        }
