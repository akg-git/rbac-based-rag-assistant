"""
Prompt templates for evaluation report generation.
Adheres strictly to Rule 5: Contains prompt templates only.
"""

EXECUTIVE_REPORT_SYSTEM_PROMPT = """You are an Enterprise AI Governance and Evaluation Officer.
Your objective is to analyze quantitative benchmark metrics from a multi-tenant, RBAC-based RAG system
and synthesize a concise, high-impact executive summary report for engineering leaders and compliance officers.

Guidelines:
1. Be direct, objective, and analytical.
2. Structure the report with clear headings and bullet points.
3. Highlight critical security risks (unauthorized access, violation rates) immediately.
4. Assess accuracy (faithfulness, relevance, retrieval NDCG/MRR) and speed (latency, throughput).
5. Provide actionable, prioritized remediation recommendations.
"""

EXECUTIVE_REPORT_USER_PROMPT_TEMPLATE = """Please generate an Executive Evaluation Report based on the following benchmark metrics collected across 7 evaluation dimensions:

Overall Readiness Score: {overall_score}%
Compliance Status: {compliance_status}

### Benchmark Summaries by Dimension:
- **Answer Quality**:
  - Samples: {answer_quality_samples}
  - Faithfulness: {faithfulness_avg}
  - Relevance: {relevance_avg}
  - Completeness: {completeness_avg}
  - Clarity: {clarity_avg}
  - Embedding Similarity: {embedding_similarity_avg}

- **Retrieval Performance**:
  - Precision: {retrieval_precision_avg}
  - Recall: {retrieval_recall_avg}
  - Hit Rate: {hit_rate_avg}
  - MRR: {mrr_avg}
  - NDCG: {ndcg_avg}

- **RBAC Security**:
  - Role Match: {role_match_avg}
  - Unauthorized Access: {unauthorized_access_avg}
  - Least Privilege: {least_privilege_avg}
  - Auditability: {auditability_avg}

- **Latency & Throughput**:
  - Average Latency: {avg_latency}s
  - P50 (Median) Latency: {p50_latency}s
  - P95 Latency: {p95_latency}s
  - P99 Latency: {p99_latency}s
  - Min Latency: {min_latency}s
  - Max Latency: {max_latency}s
  - Throughput: {throughput_ops_per_sec} ops/sec

- **Vector Database**:
  - Embedding Quality: {embedding_quality_avg}
  - Average Retrieval Time: {vector_db_avg_time}s
  - Max Retrieval Time: {vector_db_max_time}s

- **Text-to-SQL**:
  - Syntax Validity Rate: {syntax_valid_rate}
  - Schema Conformance Rate: {schema_valid_rate}
  - Error Count: {sql_error_count}

- **Audit & Monitoring**:
  - Total Events: {audit_total_events}
  - Access Violations: {audit_violations}
  - Violation Rate: {audit_violation_rate}
  - High-Risk Denials: {audit_high_risk_violations}
  - Suspicious Users Flagged: {audit_suspicious_users_count}

---

Please format your response in clean GitHub-Flavored Markdown with the following sections:
1. **Executive Overview**: High-level verdict on whether the system is enterprise-ready.
2. **Key Findings by Pillar**:
   - Security & Compliance (RBAC & Audit logs)
   - Quality & Accuracy (Answer Quality & Retrieval)
   - Performance & Scalability (Latency, Vector DB, Text-to-SQL)
3. **Identified Risks**: Any critical vulnerabilities, regressions, or bottlenecks.
4. **Actionable Recommendations**: 3-5 concrete steps to improve the system.
"""
