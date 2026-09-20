# DocuFi Architecture and Technology Stack

## System shape

DocuFi is a two-process application:

```text
Streamlit frontend
        |
        | HTTP Basic + JSON/multipart REST calls
        v
FastAPI API
  |-- authentication and RBAC
  |-- query classifier --> SQL path --> DuckDB
  |                      \ RAG path --> ChromaDB + Groq
  |-- document upload --> SQLite metadata + DuckDB CSV table + ChromaDB
  \-- evaluation package --> raw results and summaries
```

## Technology choices

| Concern | Current implementation | Design reason |
|---|---|---|
| Language | Python 3.10+ | Shared language for API, data processing, LLM orchestration, and evaluation |
| API | FastAPI with APIRouter and Pydantic | Typed request handling and async-friendly REST endpoints |
| UI | Streamlit | Rapid internal data-assistant interface with role-specific views |
| Auth | HTTP Basic, Passlib/Argon2 | Simple prototype authentication with hashed stored passwords |
| Metadata store | SQLite | Lightweight local store for users, roles, documents, and embedding state |
| Structured analytics | DuckDB | Embedded analytical SQL engine for uploaded CSV tables |
| Vector store | ChromaDB, persistent under `chroma_db` | Local semantic retrieval with metadata filters |
| Embeddings | Hugging Face `sentence-transformers/all-MiniLM-L6-v2` | Compact general-purpose text embeddings |
| LLM | Groq `llama-3.3-70b-versatile` | Query classification, SQL generation, and answer generation |
| Orchestration | LangChain packages | Prompting, document splitting, retrieval chains, and model adapters |
| Optional reranking | Cohere `rerank-english-v3.0` | Intended relevance refinement after vector retrieval |
| Data processing | Pandas and NumPy | CSV ingestion, tabular conversion, and evaluator inputs |
| Testing | `unittest` tests under `app/**/tests` | Component checks for evaluators, authorization, and SQL safety |

## Repository map

```text
app/
  main.py                         FastAPI app, startup/shutdown, router registration
  authentication/                 HTTP Basic and Argon2 password helpers
  routes/                         chat, document, and user endpoints plus tests
  models/                         Pydantic request models
  schemas/                        SQLite and DuckDB initialization/access
  utils/
    query_classifier.py           SQL vs RAG classification
    rag_module.py                 loading, splitting, embedding, retrieval chain
    rag_chain.py                  async RAG handler and source extraction
    sql_query.py                  table allowlist, SQL generation/validation/execution
  DocuFi-Frontend/                Streamlit login, role UI, chat, admin, upload flows
  rag_evaluator/                  evaluator implementations, runners, tests, reports
resources/data/                   seed departmental knowledge files
static/uploads/                   uploaded files grouped by role
static/data/                      DuckDB database file
chroma_db/                        persistent Chroma database
assets/                           frontend styling/assets
docs/                             project vision, requirements, and architecture references
```

## Main data flows

### Startup

`app.main` loads environment variables, initializes SQLite tables and DuckDB metadata, and registers the three routers. SQLite also creates a demo `admin` / `admin123` C-Level account if absent. The RAG module initializes embeddings, Chroma, and Groq/LangChain clients during import and currently requires Groq, LangChain, and Cohere keys.

### Upload and indexing

An authenticated C-Level user uploads a supported file and selects an existing role. The file is persisted under `static/uploads/<Role>/`. CSV content becomes a DuckDB table and all files receive SQLite document metadata with `embedded = 0`. The indexer loads pending files, converts them to LangChain `Document` objects, splits them at `1000/200`, writes them to Chroma with role/source metadata, and marks successful records embedded.

### Chat

The chat endpoint authenticates first, classifies the question, and routes to SQL or RAG. The SQL path uses a catalog-derived role allowlist and multiple validation gates before execution. The RAG handler runs the synchronous LangChain chain in a thread executor and returns the answer plus source filenames. SQL errors that are not authorization errors invoke the RAG path as a fallback.

## Security and consistency decisions

- Role filters are applied in the vector retriever rather than only in the frontend.
- SQL access is allowlisted from `tables_metadata` and checked again against parsed references.
- SQL execution is read-only by policy through direct-`SELECT` validation and `EXPLAIN`.
- Passwords are stored as Argon2 hashes, not plaintext.
- The server-side authenticated role is authoritative; the extra frontend role field is not part of the Pydantic chat request and is ignored.

## Current limitations to keep visible

- HTTP Basic credentials are sent on each request; logout is client-side only.
- The default demo credential must be removed or replaced before deployment.
- Operational embedding endpoints are currently unauthenticated.
- Upload filename/path handling needs sanitization and stronger validation.
- The optional reranker path is not currently wired into the production chat call and the helper returns before constructing the contextual compression retriever.
- Module-level initialization requires external API keys and may make imports fail in environments without configuration.
- The master evaluation pipeline uses sample inputs for some dimensions and leaves final report generation as a placeholder.

## Run and test reference

From the repository root:

```powershell
uvicorn app.main:app --reload
streamlit run app/DocuFi-Frontend/landing_page.py
python -m app.rag_evaluator.evaluation_pipelines
python -m unittest discover -s app -p "test_*.py" -v
```

Required environment variables include `GROQ_API_KEY`, `LANGCHAIN_API_KEY`, and `COHERE_API_KEY`; `HF_API_KEY` is optional in the current embedding configuration. The broader dependency set is maintained in `requirements.txt`, while `pyproject.toml` currently declares only the FastAPI starter dependency.

```text
Default Credentials
================================

C-Level
admin	admin123	C-level
admin2	admin456	C-level
lead_engr lengr		C-level

General
user1	user123		General
user2	user456		General
user 3 user 345 General

HR
hr1	hr111		HR
hr2	hr222		HR
hr3 hr333 HR

Engineer
engr1	eng_1.1		Engineer
engr2 eng_2.1 Engineer

Finance
finemp1		fe.1x	Finance

Marketing
markemp_1 	memp@1  Marketing
```