# evaluation_report.py
from typing import Dict, Any, List

# Import all evaluators
from app.rag_evaluator.answer_quality.evaluator import AnswerQualityEvaluator
from app.rag_evaluator.retrieval.evaluator import RetrievalEvaluator
from app.rag_evaluator.rbac_security.evaluator import RBACSecurityEvaluator
from app.rag_evaluator.latency.evaluator import LatencyEvaluator
from app.rag_evaluator.vector_db.evaluator import VectorDBEvaluator
from app.rag_evaluator.text_to_sql.evaluator import TextToSQLEvaluator
from app.rag_evaluator.audit_monitoring.evaluator import AuditMonitoringEvaluator

class EvaluationReport:
    def __init__(self, schema: Dict[str, List[str]], role_permissions: Dict[str, List[str]]):
        self.answer_quality = AnswerQualityEvaluator()
        self.retrieval = RetrievalEvaluator()
        self.rbac = RBACSecurityEvaluator(role_permissions)
        self.latency = LatencyEvaluator()
        self.vector_db = VectorDBEvaluator()
        self.text_to_sql = TextToSQLEvaluator(schema)
        self.audit = AuditMonitoringEvaluator()

    def generate_report(
        self,
        query: str,
        context: str,
        answer: str,
        retrieved_docs: List[str],
        relevant_docs: List[str],
        role: str,
        query_actions: List[str],
        query_embedding,
        doc_embeddings,
        retrieval_times: List[float],
        sql: str,
    ) -> Dict[str, Any]:
        """Run all evaluators and return consolidated report."""

        report = {
            "answer_quality": self.answer_quality.llm_judge(query, context, answer),
            "retrieval": self.retrieval.evaluate(retrieved_docs, relevant_docs),
            "rbac_security": self.rbac.evaluate_query(role, query_actions),
            "latency": self.latency.measure_latency(lambda: "dummy"),
            "vector_db": self.vector_db.evaluate(query_embedding, doc_embeddings, retrieval_times),
            "text_to_sql": self.text_to_sql.evaluate(sql),
            "audit_monitoring": self.audit.evaluate_security(),
        }
        return report
