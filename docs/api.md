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

