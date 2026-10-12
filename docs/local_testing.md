# Local Testing

## `.env` for Groq and SQL Server Express

Use this shape for local testing:

```dotenv
APP_ENV=local
APP_NAME=Enterprise AI Chatbot
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

AUTH_ENABLED=false
JWT_SECRET=change-me
RATE_LIMIT_PER_MINUTE=60

LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_groq_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
VLLM_BASE_URL=http://localhost:8001/v1

EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-large
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=enterprise_knowledge
QDRANT_ENABLED=true
EMBEDDING_DIMENSION=384

SQLSERVER_DSN=
SQLSERVER_HOST=DESKTOP-CE9MBJQ\SQLEXPRESS
SQLSERVER_DATABASE=EnterpriseChatbotDemo
SQLSERVER_USER=
SQLSERVER_PASSWORD=
SQLSERVER_DRIVER=ODBC Driver 17 for SQL Server
SQLSERVER_TRUSTED_CONNECTION=true
SQLSERVER_ENCRYPT=false
```

Other LLM options:

- `LLM_PROVIDER=mock`: no key, deterministic local testing.
- `LLM_PROVIDER=openai`: set `OPENAI_API_KEY` and an OpenAI model.
- `LLM_PROVIDER=vllm`: set `VLLM_BASE_URL` for an OpenAI-compatible local/server endpoint.
- `anthropic`, `gemini`, and `ollama` are configured in settings but need provider client implementations before production use.

## SQL Server Demo Data

Run this in SQL Server Management Studio or Azure Data Studio:

```sql
:r database/create_demo_product_sales.sql
```

If `:r` is not enabled, open `database/create_demo_product_sales.sql` and run the script manually.

Test SQL query:

```sql
SELECT TOP 10 ProductName, Category, SUM(NetRevenue) AS Revenue
FROM dbo.ProductSales
GROUP BY ProductName, Category
ORDER BY Revenue DESC;
```

## Vector DB / Document Ingestion

Start Qdrant:

```powershell
docker run -p 6333:6333 -v ${PWD}\qdrant_storage:/qdrant/storage qdrant/qdrant:v1.10.1
```

Then ingest the sample policy into RAG/Qdrant:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" -Method Post -ContentType "application/json" -Body '["sample_data/policies.md"]'
```

## Run Commands

Install:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Start API:

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Start UI in another terminal:

```powershell
streamlit run ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Smoke test API:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Ask SQL:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Show top products by revenue from SQL database","session_id":"sql-demo","files":[]}' | ConvertTo-Json -Depth 8
```

Ask RAG:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the enterprise data policy and summarize access requirements","session_id":"rag-demo","files":[]}' | ConvertTo-Json -Depth 8
```
