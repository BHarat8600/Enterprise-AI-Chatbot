# API Documentation

## `GET /health`

Returns service health and environment.

## `POST /upload`

Uploads documents and returns local paths for later chat or RAG ingestion.

## `POST /ingest`

Accepts a JSON list of file paths and indexes them into the RAG pipeline.

## `POST /chat`

Request:

```json
{
  "query": "Summarize the uploaded policy and compare with SQL metadata",
  "session_id": "demo",
  "files": ["sample_data/policies.md"]
}
```

Response includes answer, plan, tool results, citations, guardrail decision, judge scores, metrics, and timeline.

## Database workspace

`GET /database/defaults` returns non-secret SQL Server/PostgreSQL defaults from
the API's environment. `POST /database/test` accepts a connection configuration
and returns a connection status without exposing credentials.

`POST /chat` and `POST /chat/stream` accept these optional fields:

```json
{
  "query": "Show revenue by region",
  "session_id": "unique-chat-id",
  "automatic_mode": true,
  "defer_database_execution": true,
  "database": {"engine": "postgresql"}
}
```

When deferred, a database query is investigated and compiled but not executed.
`status=query_ready` includes the SQL draft in `tool_results`. Set connection
overrides inside `database`: `host`, `database`, `username`, `password`, plus
SQL Server `trusted_connection`, `driver`, `dsn`, `encrypt`, or PostgreSQL
`port`, `sslmode`. Omitted values use `.env`; changed identity never reuses the
default password. Credentials are not included in model prompts or responses.

`POST /database/execute` executes without any LLM calls:

```json
{
  "session_id": "unique-chat-id",
  "database": {"engine": "postgresql"},
  "sql": "SELECT region, SUM(amount) AS revenue FROM public.sales GROUP BY region ORDER BY revenue DESC"
}
```

The response includes `rows` (up to five), `columns`, `row_count`, `column_count`,
`report_id`, `sql`, `llm_calls=0`, and `total_tokens=0`. Download all rows from that
execution with `GET /database/reports/{report_id}?session_id=...` within one hour.
This endpoint accepts only a single read-only SELECT, including safe CTEs.

For existing API clients, `defer_database_execution` defaults to false to preserve
the previous automatic execution and LLM assessment behavior. Use true plus the
dedicated executor to keep database result rows out of the LLM, as the UI does.
See [database_workspace.md](database_workspace.md) for setup and limitations.

## Deep SQL Automatic Mode

Set `deep_sql_automatic_mode=true` on `/chat` or `/chat/stream` to use the separate
SQL investigation loop. It supports both database engines, independently
investigates schema and categorical distinct values, and returns `query_ready`
only after SQL compilation and goal review. It never executes the final data
query automatically. `tool_results[].output` includes `deep_sql`, `rounds`,
`goal_achieved`, and (on success) SQL and `profiled_columns`. Unresolved requests
may return `needs_clarification` with questions and alternative options, or
`insufficient_evidence`/`error` when appropriate, without releasing an unverified
query. Replies in the same session resume the pending request. Existing automatic/manual behavior is unchanged when
the flag is false. See [deep_sql_mode.md](deep_sql_mode.md).

