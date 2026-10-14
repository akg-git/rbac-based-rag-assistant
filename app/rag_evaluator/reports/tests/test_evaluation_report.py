import unittest
import tempfile
import shutil
import json
from pathlib import Path

from app.rag_evaluator.reports.evaluation_report import EvaluationReport
from app.rag_evaluator.evaluation_pipelines import archive_previous_logs


class TestEvaluationReport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.report_dir = Path(self.temp_dir)
        self.reporter = EvaluationReport(report_dir=self.report_dir)

        self.mock_summaries = {
            "answer_quality": {
                "samples": 10,
                "faithfulness_avg": 0.95,
                "relevance_avg": 0.90,
                "completeness_avg": 0.88,
                "clarity_avg": 0.92,
                "embedding_similarity_avg": 0.89,
            },
            "retrieval": {
                "samples": 10,
                "precision_avg": 0.85,
                "recall_avg": 0.90,
                "hit_rate_avg": 1.0,
                "mrr_avg": 0.92,
                "ndcg_avg": 0.88,
            },
            "rbac_security": {
                "samples": 10,
                "role_match_avg": 1.0,
                "unauthorized_access_avg": 0.0,
                "least_privilege_avg": 1.0,
                "auditability_avg": 1.0,
            },
            "latency": {
                "total_benchmarks": 5,
                "avg_latency": 0.045,
                "p50_latency": 0.042,
                "p95_latency": 0.060,
                "p99_latency": 0.075,
                "min_latency": 0.030,
                "max_latency": 0.080,
                "throughput_ops_per_sec": 22.2,
            },
            "vector_db": {
                "samples": 5,
                "embedding_quality_avg": 0.87,
                "avg_retrieval_time_avg": 0.012,
                "max_retrieval_time_avg": 0.025,
            },
            "text_to_sql": {
                "samples": 10,
                "syntax_valid_rate": 1.0,
                "schema_valid_rate": 0.95,
                "error_count": 0,
            },
            "audit_monitoring": {
                "total_events": 10.0,
                "violations": 0.0,
                "violation_rate": 0.0,
                "compliance_rate": 1.0,
                "high_risk_violations": 0.0,
                "suspicious_users_count": 0.0,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_indices_pass(self):
        indices = self.reporter.calculate_indices(self.mock_summaries)

        self.assertIn("overall_score", indices)
        self.assertIn("security_score", indices)
        self.assertIn("quality_score", indices)
        self.assertIn("performance_score", indices)
        self.assertEqual(indices["compliance_status"], "PASS")
        self.assertGreaterEqual(indices["overall_score"], 80.0)

    def test_calculate_indices_fail_on_security_violation(self):
        violated_summaries = dict(self.mock_summaries)
        violated_summaries["rbac_security"] = {
            "role_match_avg": 0.5,
            "unauthorized_access_avg": 0.6,
            "least_privilege_avg": 0.3,
            "auditability_avg": 0.5,
        }
        indices = self.reporter.calculate_indices(violated_summaries)
        self.assertEqual(indices["compliance_status"], "FAIL")

    def test_generate_final_report_in_memory(self):
        result = self.reporter.generate_final_report(self.mock_summaries)

        self.assertEqual(result["status"], "success")
        self.assertTrue(Path(result["json_path"]).exists())
        self.assertTrue(Path(result["md_path"]).exists())

        # Verify JSON content
        with open(result["json_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("evaluation_indices", data)
            self.assertIn("domain_summaries", data)
            self.assertEqual(data["evaluation_indices"]["compliance_status"], "PASS")

        # Verify Markdown content
        with open(result["md_path"], "r", encoding="utf-8") as f:
            md_text = f.read()
            self.assertIn("# Executive AI Evaluation & Readiness Report", md_text)
            self.assertIn("Overall System Readiness", md_text)

    def test_generate_final_report_from_disk(self):
        # Write mock summary files to disk
        summary_dir = self.report_dir / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)

        with open(summary_dir / "answer_quality_summary_20260914_000001.json", "w") as f:
            json.dump(self.mock_summaries["answer_quality"], f)
        with open(summary_dir / "rbac_security_summary_20260914_000001.json", "w") as f:
            json.dump(self.mock_summaries["rbac_security"], f)

        # Call with None to trigger disk loading
        result = self.reporter.generate_final_report(summaries=None)

        self.assertEqual(result["status"], "success")
        self.assertTrue(Path(result["json_path"]).exists())

    def test_archive_previous_logs(self):
        log_dir = self.report_dir / "evaluation_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        test_log = log_dir / "evaluation_pipelines.log"

        # Write dummy logs
        with open(test_log, "w", encoding="utf-8") as f:
            f.write("Line 1: pipeline started\nLine 2: pipeline finished\n")

        self.assertGreater(test_log.stat().st_size, 0)

        # Trigger archival
        archive_previous_logs(log_dir)

        # Check archives directory
        archives_dir = log_dir / "archives"
        self.assertTrue(archives_dir.exists())

        archived_files = list(archives_dir.glob("evaluation_pipelines_*.*"))
        self.assertGreaterEqual(len(archived_files), 1)
        # Check that extension is .7z or .zip
        self.assertTrue(any(f.suffix in [".7z", ".zip"] for f in archived_files))

        # Check that active log file was truncated
        self.assertEqual(test_log.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
