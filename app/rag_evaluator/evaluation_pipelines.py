import logging

from app.utils.rag_module import vectorstore, model 

from langchain_classic.chains import RetrievalQA
# from langchain.schema import Document
import pandas as pd
import numpy as np
import time, os, json
from groq import Groq

from pathlib import Path
from datetime import datetime

from app.rag_evaluator.answer_quality.runner import AnswerQualityRunner
from app.rag_evaluator.retrieval.runner import RetrievalRunner
from app.rag_evaluator.rbac_security.runner import RbacSecurityRunner
from app.rag_evaluator.latency.runner import LatencyRunner
from app.rag_evaluator.vector_db.runner import VectorDBRunner
from app.rag_evaluator.audit_monitoring.runner import AuditMonitoringRunner
from app.rag_evaluator.text_to_sql.runner import TextToSQLRunner

# ==========================================
# Configuration
# ==========================================

DATA_DIR = Path("resources/data")
REPORT_DIR = Path("app/rag_evaluator/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = REPORT_DIR / Path("evaluation_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
timestamp = time.strftime("%Y%m%d_%H%M%S")
log_file = LOG_DIR / f"evaluation_pipeline_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "evaluation_pipeline.log", mode="a", encoding="utf-8")
    ],
    force=True,
)

MODEL_NAME = "llama-3.3-70b-versatile"

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

    # ==========================================
    # Load Documents
    # ==========================================

    def load_source_documents(self, data_dir=DATA_DIR):
        documents = []

        for role_dir in data_dir.iterdir():

            if not role_dir.is_dir():
                continue

            role = role_dir.name.lower()

            for file in role_dir.glob("*"):

                if file.suffix.lower() not in [".txt", ".md", ".csv"]:
                    continue
                
                if file.suffix.lower() == ".csv":
                    import pandas as pd
                    df = pd.read_csv(file)
                    content = df.to_string()
                else:
                    with open(file, "r", encoding="utf-8") as f:
                        content = f.read()

                documents.append({
                    "role": role,
                    "source": file.name,
                    "content": content
                })

        return documents

    # ==========================================
    # GENERATE QA PAIRS
    # ==========================================
    def generate_qa_pairs(self, text_chunk, num_questions=1):

        # actual_prompt = """There are 10 documents present in total under resources/data with .md and .csv extensions, each document is associated with a specific role. Carefully visit each docuemnt and
        #                 generate total {num_questions} unique factual questions across 10 docuemnts and exactly one question from each document that satisfy all conditions:"""

        prompt = f"""
                You are generating evaluation questions for an enterprise RAG system.

                There are 5 departments present in total under resources/data with .md and .csv extensions, each departments is associated with a specific role. Carefully visit each departments and
                generate total 5 unique factual QA pairs across departments that satisfy all conditions:

                - answer must be concise
                - answer should contain only necessary information
                - answerable directly from the document
                - specific and objective
                - non-overlapping
                - cover different sections of the document
                - avoid yes/no questions
                - avoid duplicate meaning

                Document:
                \"\"\"
                {text_chunk}
                \"\"\"

                Return ONLY valid JSON.

                Example:
                Return JSON:

                [
                {{
                    "question": "My Question1",
                    "answer": "My Question1 answer"
                }}
                ]
                """
        try:
            response = self.groq_client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = response.choices[0].message.content.strip()

            # Groq sometimes wraps arrays inside object
            parsed = json.loads(response_text)

            if isinstance(parsed, dict):
                if "qa_pairs" in parsed:
                    return parsed["qa_pairs"]

                if "questions" in parsed:
                    return parsed["questions"]

            if isinstance(parsed, list):
                return parsed

            return []
        
        except Exception as e:
            print(f"QA generation failed: {e}")
            return []

    # ==========================================
    # Build Dataset
    # ==========================================

    def generate_qa_dataset(self, output_csv="sample_qa_pairs.csv"):

        documents = self.load_source_documents(DATA_DIR)

        qa_list = []

        for doc in documents:

            print(f"Generating QA pairs for {doc['source']} ({doc['role']})")
            qa_pairs = self.generate_qa_pairs(doc["content"], num_questions=3)

            if len(qa_pairs) < 3:
                print(f"Warning: only {len(qa_pairs)} questions generated for {doc['source']}")

            for qa in qa_pairs:
                retrieved_docs = []
                try:
                    raw_hits = vectorstore.similarity_search(
                        qa["question"],
                        k=4,
                        filter={"role": doc["role"]}
                    )
                    retrieved_docs = [hit.page_content for hit in raw_hits]
                except Exception as retrieve_error:
                    print(f"Retrieval lookup failed for '{qa['question']}': {retrieve_error}")

                relevant_docs = [doc["content"]]
                if not retrieved_docs:
                    retrieved_docs = relevant_docs

                qa_list.append({
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "role": doc["role"],
                    "source": doc["source"],
                    "retrieved_docs": retrieved_docs,
                    "context": "\n".join(retrieved_docs),
                    "relevant_docs": relevant_docs,
                })

                time.sleep(1.2)
            
        output_file = self.raw_results_dir / f"qa_dataset_{self.timestamp}.csv"
        pd.DataFrame(qa_list).to_csv(output_file, index=False)

        print(f"\nGenerated {len(qa_list)} QA pairs.")
        print(f"Saved to: {output_file}")

        return qa_list


    # Run Answer Quality Evaluation
    def run_answer_quality_evaluation(self, qa_dataset):
        result_df, summary = self.answer_quality_runner.run(qa_dataset)
        print("Answer Quality Evaluation completed.")
        print("Summary:", summary)

        return result_df, summary
    

    # Run Answer Quality Evaluation
    def run_retrieval(self, qa_dataset):
        result_df, summary = self.retrieval_runner.run(qa_dataset)
        print("Retrieval Evaluation completed.")
        print("Summary:", summary)

        return result_df, summary

    # Run RBAC Security Evaluation
    def run_rbac_security(self, qa_dataset):
        result_df, summary = self.rbac_security_runner.run(qa_dataset)
        print("RBAC Security Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    # Run Latency Evaluation
    def run_latency(self, functions_to_test):
        result_df, summary = self.latency_runner.run(functions_to_test)
        print("Latency Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    # Vector DB Evaluation:
    def run_vector_db(self, queries):
        result_df, summary = self.vector_db_runner.run(queries)
        print("Vector DB Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    def run_text_to_sql(self, qa_dataset):
        result_df, summary = self.text_to_sql_runner.run(qa_dataset)
        print("Text To SQL Evaluation completed.")
        print("Summary:", summary)
        return result_df, summary

    def run_audit_monitoring(self):

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

    def generate_final_report(self):
        print("Future implementation: reports/evaluation_report.py")

    # ----------------------------------------------------
    # MASTER EXECUTION
    # ----------------------------------------------------

    def run(self):

        print( "Generating QA Dataset...")
        qa_dataset = (self.generate_qa_dataset())
        
        print("Running Answer Quality Evaluation...")
        self.run_answer_quality_evaluation(qa_dataset)
        print("Answer Quality Evaluation completed successfully.")

        print("Running Retrieval Evaluation...")
        self.run_retrieval(qa_dataset)
        print("Retrieval Evaluation completed successfully.")

        print("Running RBAC Security Evaluation...")
        self.run_rbac_security(qa_dataset)
        print("RBAC Evaluation completed successfully.")

        print("Running Latency Evaluation...")
        self.run_latency([
            ("dummy_function", lambda x: x*2, [5], {}),
        ])
        print("Latency Evaluation completed successfully.")

        print("Running Vector DB Evaluation...")
        self.run_vector_db([
            {
                "query": "What is AI?",
                "query_embedding": np.array([0.1, 0.2, 0.3]),
                "doc_embeddings": np.array([[0.1,0.2,0.3],[0.2,0.1,0.0],[0.3,0.3,0.3]]),
                "retrieval_times": [0.01, 0.02, 0.03]
            }
        ])

        print("Running Text To SQL Evaluation...")
        self.run_text_to_sql(qa_dataset)
        print("Text To SQL Evaluation completed successfully.")

        print("Running Audit Monitoring Evaluation...")
        self.run_audit_monitoring()
        print("Audit Monitoring Evaluation completed successfully.")

# ==========================================
# Entry Point
# ==========================================

if __name__ == "__main__":

    pipeline = EvaluationPipeline()
    pipeline.run()