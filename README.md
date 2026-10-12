# Enterprise AI Chatbot

Production-oriented multi-agent chatbot scaffold with FastAPI, Streamlit, SQL Server tooling, document/PDF tooling, hybrid RAG, guardrails, evaluation, structured logging, and observability.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env
uvicorn api.main:app --reload
```

In another terminal:

```bash
streamlit run ui/streamlit_app.py
```

For Groq, SQL Server Express, Qdrant ingestion, and sample production-like SQL data, see [docs/local_testing.md](docs/local_testing.md).

For Subscription_Analysis end-to-end SQL, PDF, document, RAG, and multi-tool tests, see [docs/subscription_analysis_testing.md](docs/subscription_analysis_testing.md).

If SQL Server returns "not configured" or connection errors, see [docs/sql_server_fix.md](docs/sql_server_fix.md).

## Example

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Retrieve the enterprise data policy\",\"session_id\":\"demo\",\"files\":[]}"
```

## Production Features

- Agentic execution plan before tool use
- SQL Server query validation and read-only execution
- PDF, DOCX, TXT, Markdown, CSV, and Excel support
- Hybrid RAG structure with BM25 and Qdrant-ready configuration
- Short-term/session memory and summarization
- Prompt injection, jailbreak, PII masking, output validation
- LLM judge and RAG metric logging hooks
- Prometheus metrics and OpenTelemetry tracing
- Docker, Docker Compose, CI, tests, docs, sample data

## Extending Providers

Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=vllm` for OpenAI-compatible chat completions. Other providers are represented in configuration and can be added behind `services/llm.py`.

## Diagrams

See [docs/architecture.md](docs/architecture.md).
