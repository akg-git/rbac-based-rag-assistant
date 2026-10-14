# DocuFi: Project Vision

## What is being built

DocuFi is an internal, role-aware data assistant for asking questions about company documents and structured departmental data. It combines retrieval-augmented generation (RAG) for unstructured files with natural-language-to-SQL querying for CSV-derived tables. The assistant returns an answer while preserving the authenticated user's role boundary and, where available, the source documents or generated SQL.

## Who it is for

- Employees who need fast answers from departmental reports, policies, and operational data.
- Departmental users who should see their own department's knowledge plus shared General content.
- C-Level users who need cross-department visibility and controlled administration.
- Developers and evaluators who need measurable checks for retrieval quality, answer quality, latency, vector search, SQL behavior, RBAC, and audit events.

## Why it matters

Internal knowledge is often distributed across documents and spreadsheets, while access to that knowledge is not uniform. DocuFi brings those sources behind one conversational interface and makes authorization part of the retrieval and query path, rather than relying only on UI controls. This reduces search friction, supports data-informed decisions, and creates a foundation for evaluating answer quality and security.

## Product north star

For every authenticated question, DocuFi should provide the most useful answer that can be supported by data the user is authorized to access. It should avoid guessing, expose provenance when possible, and fail closed when a requested structured dataset is outside the user's role boundary.

## Current implementation snapshot

- FastAPI backend with HTTP Basic authentication and Argon2 password hashing.
- Streamlit frontend with role-specific chat, upload, and administration views.
- ChromaDB vector retrieval using Hugging Face `all-MiniLM-L6-v2` embeddings.
- Groq `llama-3.3-70b-versatile` for query classification, SQL generation, and RAG answers.
- SQLite for users, roles, and document-indexing metadata.
- DuckDB for structured CSV tables and catalog metadata.
- Evaluation runners for answer quality, retrieval, RBAC security, latency, vector DB behavior, text-to-SQL, and audit monitoring.

## Resume-ready skill tags

`Python` `FastAPI` `Streamlit` `REST APIs` `HTTP Basic Auth` `Argon2` `RBAC` `RAG` `LangChain` `ChromaDB` `Hugging Face Embeddings` `Groq LLM` `Natural Language to SQL` `DuckDB` `SQLite` `Prompt Engineering` `Document Ingestion` `Evaluation Pipelines` `Retrieval Metrics` `SQL Security Validation` `Audit Logging`

## Boundary of this vision

This document describes the implemented prototype and its direction. Production hardening such as token/session revocation, upload filename sanitization, authenticated operational endpoints, stronger observability, and a consolidated final evaluation report remains future work.