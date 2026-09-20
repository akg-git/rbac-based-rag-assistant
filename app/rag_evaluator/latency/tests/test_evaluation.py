import unittest
import tempfile
import shutil
import time
from pathlib import Path

from app.rag_evaluator.latency.evaluator import LatencyEvaluator
from app.rag_evaluator.latency.runner import LatencyRunner


class TestLatencyEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = LatencyEvaluator()

    def test_empty_latencies(self):
        result = self.evaluator.evaluate([])
        self.assertEqual(result["avg_latency"], 0.0)
        self.assertEqual(result["p50_latency"], 0.0)
        self.assertEqual(result["p95_latency"], 0.0)
        self.assertEqual(result["p99_latency"], 0.0)
        self.assertEqual(result["min_latency"], 0.0)
        self.assertEqual(result["max_latency"], 0.0)
        self.assertEqual(result["throughput_ops_per_sec"], 0.0)

    def test_single_latency_float(self):
        result = self.evaluator.evaluate(0.05)
        self.assertAlmostEqual(result["avg_latency"], 0.05, places=5)
        self.assertAlmostEqual(result["min_latency"], 0.05, places=5)
        self.assertAlmostEqual(result["max_latency"], 0.05, places=5)
        self.assertAlmostEqual(result["throughput_ops_per_sec"], 20.0, places=1)

    def test_multiple_latencies_distribution(self):
        # 10 samples from 0.01 to 0.10
        samples = [round(i * 0.01, 2) for i in range(1, 11)]
        result = self.evaluator.evaluate(samples)

        self.assertAlmostEqual(result["avg_latency"], 0.055, places=3)
        self.assertAlmostEqual(result["min_latency"], 0.01, places=3)
        self.assertAlmostEqual(result["max_latency"], 0.10, places=3)
        self.assertGreater(result["p95_latency"], result["p50_latency"])
        self.assertGreaterEqual(result["p99_latency"], result["p95_latency"])
        self.assertGreater(result["throughput_ops_per_sec"], 0.0)

    def test_zero_latency_throughput(self):
        result = self.evaluator.evaluate([0.0])
        self.assertEqual(result["avg_latency"], 0.0)
        self.assertEqual(result["throughput_ops_per_sec"], 0.0)

    def test_runner_execution(self):
        temp_dir = tempfile.mkdtemp()
        try:
            runner = LatencyRunner(report_dir=Path(temp_dir))

            def sample_add(a, b):
                time.sleep(0.005)
                return a + b

            functions_to_test = [
                ("addition_benchmark", sample_add, [2, 3], {}),
            ]

            df, summary = runner.run(functions_to_test, iterations=3)

            self.assertEqual(len(df), 1)
            self.assertEqual(df.iloc[0]["function"], "addition_benchmark")
            self.assertEqual(df.iloc[0]["iterations"], 3)
            self.assertIn("avg_latency", df.columns)
            self.assertIn("p50_latency", df.columns)
            self.assertIn("p95_latency", df.columns)
            self.assertIn("throughput_ops_per_sec", df.columns)

            self.assertEqual(summary["total_benchmarks"], 1)
            self.assertIn("avg_latency", summary)

            raw_files = list((Path(temp_dir) / "raw_results").glob("*.csv"))
            summary_files = list((Path(temp_dir) / "summaries").glob("*.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(len(summary_files), 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
