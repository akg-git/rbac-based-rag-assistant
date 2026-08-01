import unittest
import time
from app.rag_evaluator.latency.evaluator import LatencyEvaluator

class TestLatencyEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = LatencyEvaluator()

    def dummy_function(self, x):
        time.sleep(0.1)
        return x * 2

    def test_measure_latency(self):
        result = self.evaluator.measure_latency(self.dummy_function, 5)
        self.assertIn("latency_seconds", result)
        self.assertIn("throughput_ops_per_sec", result)
        self.assertIn("result", result)
        self.assertEqual(result["result"], 10)
        self.assertGreaterEqual(result["latency_seconds"], 0.1)

if __name__ == "__main__":
    unittest.main()
