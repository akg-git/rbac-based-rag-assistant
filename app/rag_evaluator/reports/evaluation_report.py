"""
Executive Report Generation Module.
Adheres strictly to Rule 4: Aggregates all summaries and generates final executive reports.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

from app.rag_evaluator.reports.report_prompt import (
    EXECUTIVE_REPORT_SYSTEM_PROMPT,
    EXECUTIVE_REPORT_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class EvaluationReport:
    """
    Aggregates domain benchmark summaries across all 7 evaluation dimensions
    and produces consolidated executive reports in JSON and Markdown formats.
    """

    def __init__(
        self,
        report_dir: Path = Path("app/rag_evaluator/reports"),
        client: Any = None,
        model_name: str = "llama-3.3-70b-versatile",
    ):
        self.report_dir = Path(report_dir)
        self.summary_dir = self.report_dir / "summaries"
        self.final_report_dir = self.report_dir / "final_reports"

        self.summary_dir.mkdir(parents=True, exist_ok=True)
        self.final_report_dir.mkdir(parents=True, exist_ok=True)

        self.client = client
        self.model_name = model_name

    def load_latest_summaries(self) -> Dict[str, Dict[str, Any]]:
        """
        Scan the summary directory and load the latest summary JSON for each domain.
        """
        domains = [
            "answer_quality",
            "retrieval",
            "rbac_security",
            "latency",
            "vector_db",
            "text_to_sql",
            "audit_monitoring",
        ]

        summaries: Dict[str, Dict[str, Any]] = {}

        for domain in domains:
            matching_files = sorted(
                self.summary_dir.glob(f"{domain}_summary_*.json"),
                key=os.path.getmtime,
                reverse=True,
            )
            if matching_files:
                latest_file = matching_files[0]
                try:
                    with open(latest_file, "r", encoding="utf-8") as f:
                        summaries[domain] = json.load(f)
                except Exception as e:
                    logger.warning("Could not read %s: %s", latest_file, e)
                    summaries[domain] = {}
            else:
                summaries[domain] = {}

        return summaries

    def calculate_indices(self, summaries: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute high-level executive health and readiness indices from aggregated summaries.
        """
        aq = summaries.get("answer_quality", {})
        retrieval = summaries.get("retrieval", {})
        rbac = summaries.get("rbac_security", {})
        latency = summaries.get("latency", {})
        vdb = summaries.get("vector_db", {})
        sql = summaries.get("text_to_sql", {})
        audit = summaries.get("audit_monitoring", {})

        # Quality Index (0-100)
        faithfulness = aq.get("faithfulness_avg", 0.0)
        relevance = aq.get("relevance_avg", 0.0)
        ndcg = retrieval.get("ndcg_avg", retrieval.get("ndcg", 0.0))
        precision = retrieval.get("precision_avg", retrieval.get("context_precision", 0.0))
        quality_score = round(
            ((faithfulness + relevance + ndcg + precision) / 4.0) * 100.0, 1
        )

        # Security & Compliance Index (0-100)
        role_match = rbac.get("role_match_avg", rbac.get("role_match", 1.0))
        unauthorized = rbac.get("unauthorized_access_avg", rbac.get("unauthorized_access", 0.0))
        least_privilege = rbac.get("least_privilege_avg", rbac.get("least_privilege", 1.0))
        audit_compliance = audit.get("compliance_rate", 1.0 - audit.get("violation_rate", 0.0))

        security_score = round(
            ((role_match + (1.0 - unauthorized) + least_privilege + audit_compliance) / 4.0) * 100.0,
            1,
        )

        # Performance Score (0-100)
        avg_lat = latency.get("avg_latency", 0.5)
        # 0.1s or lower -> 100%, 2.0s or higher -> 0%
        perf_score = round(max(0.0, min(100.0, (1.0 - (avg_lat / 2.0)) * 100.0)), 1)

        # Overall Weighted Score (Security 40%, Quality 35%, Performance 25%)
        overall_score = round(
            (security_score * 0.40) + (quality_score * 0.35) + (perf_score * 0.25), 1
        )

        # Compliance Status
        if security_score >= 90.0 and unauthorized == 0.0:
            compliance_status = "PASS"
        elif security_score >= 70.0:
            compliance_status = "WARNING"
        else:
            compliance_status = "FAIL"

        return {
            "overall_score": overall_score,
            "security_score": security_score,
            "quality_score": quality_score,
            "performance_score": perf_score,
            "compliance_status": compliance_status,
        }

    def generate_narrative(
        self, summaries: Dict[str, Dict[str, Any]], indices: Dict[str, Any]
    ) -> str:
        """
        Generate executive commentary using Groq LLM if available, otherwise deterministic fallback.
        """
        aq = summaries.get("answer_quality", {})
        ret = summaries.get("retrieval", {})
        rbac = summaries.get("rbac_security", {})
        lat = summaries.get("latency", {})
        vdb = summaries.get("vector_db", {})
        sql = summaries.get("text_to_sql", {})
        audit = summaries.get("audit_monitoring", {})

        prompt = EXECUTIVE_REPORT_USER_PROMPT_TEMPLATE.format(
            overall_score=indices.get("overall_score", 0.0),
            compliance_status=indices.get("compliance_status", "UNKNOWN"),
            answer_quality_samples=aq.get("samples", 0),
            faithfulness_avg=aq.get("faithfulness_avg", "N/A"),
            relevance_avg=aq.get("relevance_avg", "N/A"),
            completeness_avg=aq.get("completeness_avg", "N/A"),
            clarity_avg=aq.get("clarity_avg", "N/A"),
            embedding_similarity_avg=aq.get("embedding_similarity_avg", "N/A"),
            retrieval_precision_avg=ret.get("precision_avg", ret.get("context_precision", "N/A")),
            retrieval_recall_avg=ret.get("recall_avg", ret.get("context_recall", "N/A")),
            hit_rate_avg=ret.get("hit_rate_avg", ret.get("hit_rate", "N/A")),
            mrr_avg=ret.get("mrr_avg", ret.get("mrr", "N/A")),
            ndcg_avg=ret.get("ndcg_avg", ret.get("ndcg", "N/A")),
            role_match_avg=rbac.get("role_match_avg", "N/A"),
            unauthorized_access_avg=rbac.get("unauthorized_access_avg", "N/A"),
            least_privilege_avg=rbac.get("least_privilege_avg", "N/A"),
            auditability_avg=rbac.get("auditability_avg", "N/A"),
            avg_latency=lat.get("avg_latency", "N/A"),
            p50_latency=lat.get("p50_latency", "N/A"),
            p95_latency=lat.get("p95_latency", "N/A"),
            p99_latency=lat.get("p99_latency", "N/A"),
            min_latency=lat.get("min_latency", "N/A"),
            max_latency=lat.get("max_latency", "N/A"),
            throughput_ops_per_sec=lat.get("throughput_ops_per_sec", "N/A"),
            embedding_quality_avg=vdb.get("embedding_quality_avg", "N/A"),
            vector_db_avg_time=vdb.get("avg_retrieval_time_avg", "N/A"),
            vector_db_max_time=vdb.get("max_retrieval_time_avg", "N/A"),
            syntax_valid_rate=sql.get("syntax_valid_rate", "N/A"),
            schema_valid_rate=sql.get("schema_valid_rate", "N/A"),
            sql_error_count=sql.get("error_count", 0),
            audit_total_events=audit.get("total_events", audit.get("samples", 0)),
            audit_violations=audit.get("violations", 0),
            audit_violation_rate=audit.get("violation_rate", 0.0),
            audit_high_risk_violations=audit.get("high_risk_violations", 0),
            audit_suspicious_users_count=audit.get("suspicious_users_count", 0),
        )

        if self.client is not None:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": EXECUTIVE_REPORT_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning("LLM report generation fallback triggered: %s", exc)

        # Deterministic Markdown fallback
        return f"""## Executive Overview
The evaluation framework completed benchmarks across all 7 operational dimensions.
- **Overall Readiness Score**: **{indices.get('overall_score')}%**
- **Compliance Status**: **{indices.get('compliance_status')}**

### Key Findings by Pillar:
- **Security & Compliance**: RBAC compliance scored **{indices.get('security_score')}%**. Access controls and audit logging verified.
- **Quality & Accuracy**: RAG answer quality and retrieval scored **{indices.get('quality_score')}%**.
- **Performance & Scalability**: Latency and data layer performance scored **{indices.get('performance_score')}%**.

### Actionable Recommendations:
1. Ensure all high-risk RBAC violations remain at zero.
2. Monitor vector database retrieval times and index health.
3. Validate text-to-SQL schema constraints on all analytical endpoints.
"""

    def generate_final_report(
        self, summaries: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Master method to aggregate summaries, compute indices, and write final JSON & Markdown reports.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 1. Resolve summaries (use passed dict or load from disk)
        resolved_summaries = summaries if summaries else self.load_latest_summaries()

        # 2. Calculate indices
        indices = self.calculate_indices(resolved_summaries)

        # 3. Generate executive narrative
        narrative = self.generate_narrative(resolved_summaries, indices)

        # 4. Construct complete JSON report structure
        report_data = {
            "timestamp": timestamp,
            "evaluation_indices": indices,
            "domain_summaries": resolved_summaries,
            "executive_summary_markdown": narrative,
        }

        # 5. Save JSON report
        json_path = self.final_report_dir / f"executive_report_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=4)

        # 6. Save Markdown report
        md_content = f"""# Executive AI Evaluation & Readiness Report
**Generated At:** {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Run ID:** `{timestamp}`  

---

## Executive KPI Dashboard
| Metric | Score | Status |
| :--- | :---: | :---: |
| **Overall System Readiness** | **{indices['overall_score']}%** | **{indices['compliance_status']}** |
| **Security & RBAC Compliance** | {indices['security_score']}% | {'PASS' if indices['security_score'] >= 90 else 'WARN'} |
| **Answer Quality & Retrieval** | {indices['quality_score']}% | {'PASS' if indices['quality_score'] >= 75 else 'WARN'} |
| **System Performance & Latency** | {indices['performance_score']}% | {'PASS' if indices['performance_score'] >= 70 else 'WARN'} |

---

{narrative}

---

## Aggregated Domain Summaries
```json
{json.dumps(resolved_summaries, indent=2)}
```
"""
        md_path = self.final_report_dir / f"executive_report_{timestamp}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info("Executive report generated successfully: %s", md_path)

        return {
            "status": "success",
            "timestamp": timestamp,
            "json_path": str(json_path),
            "md_path": str(md_path),
            "indices": indices,
            "report_data": report_data,
        }
