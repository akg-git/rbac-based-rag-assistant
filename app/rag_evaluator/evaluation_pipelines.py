import logging
import os
import shutil
import zipfile
import subprocess
from functools import partial
from pathlib import Path
from datetime import datetime

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

from app.utils.rag_module import vectorstore
from app.utils.rag_chain import rag_handler

from app.rag_evaluator.evaluation_dataset_builder import EvaluationDatasetBuilder
from app.rag_evaluator.answer_quality.runner import AnswerQualityRunner
from app.rag_evaluator.retrieval.runner import RetrievalRunner
from app.rag_evaluator.rbac_security.runner import RbacSecurityRunner
from app.rag_evaluator.latency.runner import LatencyRunner
from app.rag_evaluator.vector_db.runner import VectorDBRunner
from app.rag_evaluator.audit_monitoring.runner import AuditMonitoringRunner
from app.utils.audit_events import AUDIT_EVENT_LOG_PATH, load_audit_events
from app.rag_evaluator.text_to_sql.runner import TextToSQLRunner
from app.rag_evaluator.reports.evaluation_report import EvaluationReport

# ==========================================
# Configuration
# ==========================================

DATA_DIR = Path("resources/data")
REPORT_DIR = Path("app/rag_evaluator/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = REPORT_DIR / Path("evaluation_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def archive_previous_logs(log_dir: Path) -> None:
    """
    Archive prior files into 7z (or zip fallback) under log_dir / 'archives'.
    """
    archives_dir = log_dir / "archives"
    archives_dir.mkdir(parents=True, exist_ok=True)

    seven_zip_exe = "C:\\Program Files\\7-Zip\\7z.exe"
    has_7z = bool(shutil.which("7z") or os.path.exists(seven_zip_exe))
    seven_zip_cmd = shutil.which("7z") or seven_zip_exe

    for output_file in log_dir.iterdir():
        if not output_file.is_file() or output_file.stat().st_size == 0:
            continue

        mtime = datetime.fromtimestamp(output_file.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
        archive_name = f"{output_file.stem}_{output_file.suffix.lstrip('.')}_{mtime}"
        archived = False

        if has_7z:
            archive_7z = archives_dir / f"{archive_name}.7z"
            try:
                subprocess.run(
                    [seven_zip_cmd, "a", "-t7z", "-y", str(archive_7z), str(output_file)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                archived = True
            except Exception:
                archived = False

        if not archived:
            archive_zip = archives_dir / f"{archive_name}.zip"
            try:
                with zipfile.ZipFile(archive_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(output_file, arcname=output_file.name)
                archived = True
            except Exception:
                pass

        if archived:
            try:
                if output_file.suffix.lower() == ".log":
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.truncate(0)
                else:
                    output_file.unlink()
            except Exception:
                pass


# Archive previous run logs before initializing logger
archive_previous_logs(LOG_DIR)

pipeline_log_path = LOG_DIR / "evaluation_pipelines.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(pipeline_log_path, mode="a", encoding="utf-8")
    ],
    force=True,
)

MODEL_NAME = os.getenv("GROQ_MODEL")

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


class EvaluationPipeline:
    def __init__(self):

        self.timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        self.base_report_dir = REPORT_DIR
        self.raw_results_dir = REPORT_DIR/ "raw_results"
        self.summary_dir = REPORT_DIR/ "summaries"
        self.final_report_dir = REPORT_DIR/ "final_reports"

        for folder in [
            self.raw_results_dir,
            self.summary_dir,
            self.final_report_dir
        ]:
            folder.mkdir(
                parents=True,
                exist_ok=True
            )

        self.answer_quality_runner = AnswerQualityRunner(report_dir=REPORT_DIR)
        self.retrieval_runner = RetrievalRunner(report_dir=REPORT_DIR)
        self.rbac_security_runner = RbacSecurityRunner(report_dir=REPORT_DIR)
        self.latency_runner = LatencyRunner(report_dir=REPORT_DIR)
        self.vector_db_runner = VectorDBRunner(report_dir=REPORT_DIR)
        self.audit_monitoring_runner = AuditMonitoringRunner(report_dir=REPORT_DIR)
        self.text_to_sql_runner = TextToSQLRunner(report_dir=REPORT_DIR)

        self.groq_client = client
        self.evaluation_dataset_builder = EvaluationDatasetBuilder(
            groq_client=self.groq_client,
            vectorstore=vectorstore,
            model_name=MODEL_NAME,
            data_dir=DATA_DIR,
            raw_results_dir=self.raw_results_dir,
            timestamp=self.timestamp,
        )

        self.evaluation_report = EvaluationReport(
            report_dir=REPORT_DIR,
            client=self.groq_client,
            model_name=MODEL_NAME,
        )

    # Run Answer Quality Evaluation
    def run_answer_quality_evaluation(self, qa_dataset):
        result_df, summary = self.answer_quality_runner.run(qa_dataset)
        print("Answer Quality Evaluation completed.")
        print("Summary:", summary)

        return result_df, summary
    

    # Run Retrieval  Evaluation
    def run_retrieval_evaluation(self, qa_dataset):
        result_df, summary = self.retrieval_runner.run(qa_dataset)
        print("Retrieval Evaluation completed.")
        print("Summary:", summary)

        return result_df, summary

    # Run RBAC Security Evaluation
    def run_rbac_security_evaluation(self, qa_dataset):
        result_df, summary = self.rbac_security_runner.run(qa_dataset)
        print("RBAC Security Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    # Run Latency Evaluation
    def run_latency_evaluation(self, functions_to_test):
        result_df, summary = self.latency_runner.run(functions_to_test)
        print("Latency Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    # Vector DB Evaluation:
    def run_vector_db_evaluation(self, k=5):
        result_df, summary = self.vector_db_runner.run(k=k)
        print("Vector DB Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    def run_text_to_sql_evaluation(self, qa_dataset):
        result_df, summary = self.text_to_sql_runner.run(qa_dataset)
        print("Text To SQL Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    def run_audit_monitoring_evaluation(self):
        persisted_events = load_audit_events(AUDIT_EVENT_LOG_PATH)

        if persisted_events:
            result_df, summary = self.audit_monitoring_runner.run(persisted_events)
        else:
            sample_events = [
                {"user": "alice", "role": "employee", "action": "read_data", "status": "granted"},
                {"user": "bob", "role": "guest", "action": "delete_data", "status": "denied"},
                {"user": "charlie", "role": "HR", "action": "update_record", "status": "granted"},
                {"user": "dave", "role": "employee", "action": "write_data", "status": "denied"},
            ]
            result_df, summary = self.audit_monitoring_runner.run(sample_events)

        print("Audit Monitoring Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    # ----------------------------------------------------
    # Final Report Trigger
    # ----------------------------------------------------

    def generate_final_report(self, summaries=None):
        """
        Trigger executive report generation from aggregated summaries.
        """
        logging.info("Triggering final executive report generation...")
        report_result = self.evaluation_report.generate_final_report(summaries)
        print("\n" + "=" * 65)
        print("FINAL EXECUTIVE REPORT GENERATED")
        print(f"Markdown Report: {report_result['md_path']}")
        print(f"JSON Report:     {report_result['json_path']}")
        print(f"Overall Score:   {report_result['indices']['overall_score']}%")
        print(f"Compliance:      {report_result['indices']['compliance_status']}")
        print("=" * 65 + "\n")
        return report_result


    # ----------------------------------------------------
    # MASTER EXECUTION
    # ----------------------------------------------------

    def run(self):
        all_summaries = {}

        for output_dir in [
            self.raw_results_dir,
            self.summary_dir,
            self.final_report_dir,
        ]:
            archive_previous_logs(output_dir)

        print("Generating QA Dataset...")
        qa_dataset = self.evaluation_dataset_builder.generate_qa_dataset()

        # Step 1: Answer Quality
        print("Running Answer Quality Evaluation...")
        _, aq_summary = self.run_answer_quality_evaluation(qa_dataset)
        all_summaries["answer_quality"] = aq_summary
        print("Answer Quality Evaluation completed successfully.")

        # Step 2: Retrieval
        print("Running Retrieval Evaluation...")
        _, ret_summary = self.run_retrieval_evaluation(qa_dataset)
        all_summaries["retrieval"] = ret_summary
        print("Retrieval Evaluation completed successfully.")

        # Step 3: RBAC Security
        print("Running RBAC Security Evaluation...")
        _, rbac_summary = self.run_rbac_security_evaluation(qa_dataset)
        all_summaries["rbac_security"] = rbac_summary
        print("RBAC Evaluation completed successfully.")

        # Step 4: Latency
        print("Running Latency Evaluation...")
        latency_workload = [
            (
                f"rag_{index + 1}",
                partial(rag_handler, question=str(item.get("question", "")), role=str(item.get("role", "general"))),
                [],
                {},
            )
            for index, item in enumerate(qa_dataset[:3])
        ]
        _, lat_summary = self.run_latency_evaluation(latency_workload, iterations=3)
        all_summaries["latency"] = lat_summary
        print("Latency Evaluation completed successfully.")

        # Step 5: Vector DB
        print("Running Vector DB Evaluation...")
        _, vdb_summary = self.run_vector_db_evaluation(k=5)
        all_summaries["vector_db"] = vdb_summary
        print("Vector DB Evaluation completed successfully.")

        # Step 6: Text To SQL
        print("Running Text To SQL Evaluation...")
        _, sql_summary = self.run_text_to_sql_evaluation(qa_dataset)
        all_summaries["text_to_sql"] = sql_summary
        print("Text To SQL Evaluation completed successfully.")

        # Step 7: Audit Monitoring
        print("Running Audit Monitoring Evaluation...")
        _, audit_summary = self.run_audit_monitoring_evaluation()
        all_summaries["audit_monitoring"] = audit_summary
        print("Audit Monitoring Evaluation completed successfully.")

        # Step 8: Final Report Generation
        print("Generating Final Executive Report...")
        report_result = self.generate_final_report(all_summaries)
        print("Evaluation Pipeline Execution Finished.")

        return report_result

# ==========================================
# Entry Point
# ==========================================

if __name__ == "__main__":

    pipeline = EvaluationPipeline()
    pipeline.run()