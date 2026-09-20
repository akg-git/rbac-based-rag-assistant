# DocuFi Requirements and Specification

## Scope

### In scope

1. Authenticate users against SQLite using HTTP Basic credentials.
2. Associate each user with one role and enforce role-based access.
3. Let C-Level users create users, create roles, delete users, and upload documents.
4. Accept `.md`, `.txt`, and `.csv` uploads. Associate every upload with an existing role.
5. Index document content into persistent ChromaDB with role and source metadata.
6. Answer authenticated questions through either RAG or structured SQL.
7. Restrict RAG retrieval to the user's role plus `general`, except C-Level, which can retrieve all indexed content.
8. Restrict SQL generation and execution to role-authorized DuckDB tables.
9. Fall back from a failed non-authorized SQL path to RAG; return HTTP 403 for authorization failures.
10. Provide evaluation runners and raw/summary report artifacts for the main quality and security dimensions.

### Out of scope or not yet implemented

- OAuth2/JWT, SSO, MFA, server-side sessions, or credential revocation.
- Multi-tenant isolation, production deployment, background job infrastructure, and horizontal scaling.
- Editing or deleting indexed documents through the API.
- A fully implemented consolidated final report; `generate_final_report` is currently a placeholder.
- Live-service benchmarking in the master evaluator; some latency, vector, and audit inputs are synthetic.

## Actors and authorization

| Actor | Read access | Administrative access |
|---|---|---|
| C-Level | All role-tagged and General content; all permitted structured tables | Create/delete users, create roles, upload documents |
| Department role, such as HR or Finance | Own role-tagged content plus General content | None |
| General | General content only | None |

Authorization is determined from the role returned by authentication. A client-supplied role must not override it.

## Input and output contracts

### Authentication and users

- `GET /login`: authenticated request; returns a welcome message and role.
- `GET /roles`: authenticated request; returns `{ "roles": [...] }`.
- `GET /user-info/{username}`: authenticated request; returns username and role or `404`.
- `POST /create-user`: multipart `username`, `password`, `role`; C-Level only; rejects unknown roles and duplicate usernames.
- `POST /delete-user`: multipart `username`, `role`; C-Level only; deletes by username.
- `POST /create-role`: multipart `role_name`; C-Level only; rejects duplicate roles.
- `GET /logout`: authenticated compatibility endpoint; the frontend clears local state, but the backend does not revoke credentials.

### Chat

Request:

```json
{"question": "What were the quarterly sales?"}
```

Response includes `user`, `role`, `mode`, `answer`, and `fallback`. Successful SQL responses may include `sql`; RAG responses may include a unique `sources` list. Empty questions return `400`.

### Documents and embeddings

- `POST /upload-docs`: multipart `file` and `role`; C-Level only.
- CSV files are loaded into DuckDB and also indexed as row-oriented text documents.
- Markdown/text files are indexed as document content.
- Successful indexing returns `embedded: true`; upload success with incomplete indexing returns `202` and `embedded: false`.
- `GET /retry-embed` retries all unembedded records.
- `GET /embedding-status` reports total, embedded, and unembedded documents.

## Processing rules

### RAG

- Splitter: `RecursiveCharacterTextSplitter`, chunk size `1000`, overlap `200`.
- Retrieval count: up to `4` documents.
- Metadata: lowercase role and source filename.
- Generation: Groq `llama-3.3-70b-versatile`, temperature `0.2`.
- Prompt behavior: use retrieved context, do not guess, explain missing data, and include sources where possible.

### Query routing and SQL

1. Groq classifies the question as `SQL` or `RAG`.
2. SQL mode obtains the role's allowed tables from DuckDB metadata.
3. Groq generates SQL from the authorized catalog.
4. Validation requires one direct `SELECT`, rejects CTEs, set operations, table functions, and administrative statements, checks referenced tables, and runs DuckDB `EXPLAIN`.
5. Results are formatted as a Markdown table.
6. Non-authorization SQL failures fall back to RAG.

## Edge cases and failure behavior

- Invalid credentials: `401`.
- Non-C-Level administrative or upload request: `403`.
- Unknown upload role, unsupported extension, missing/empty question: `400`.
- Missing knowledge-base content or failed RAG generation: structured error answer and an HTTP error at the chat boundary.
- Unknown user lookup: `404`.
- Duplicate user or role: `400`.
- Unauthorized SQL data request: `403`, without RAG fallback.
- Embedding failure after file persistence: `202`; the document remains available for retry.

## Acceptance checks

- A department user cannot retrieve another department's vector content.
- A department user cannot execute SQL against another department's table.
- C-Level can retrieve across departments and administer users/roles/uploads.
- A valid RAG answer includes source names when context metadata is returned.
- A valid SQL answer exposes the generated SQL and formatted result.
- Existing unit tests continue to cover SQL security, upload authorization, and evaluator components.