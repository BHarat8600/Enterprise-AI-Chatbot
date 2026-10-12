# End-to-End Test Guide (From Scratch)

This guide is meant to be followed step by step on a fresh machine or fresh clone of this project. It covers setup, configuration, backend start-up, UI testing, SQL demo testing, RAG demo testing, and sample queries you can run during live demos.

## 1) Requirements

Before you start, make sure you have:

- Python 3.12+
- Git
- SQL Server Express or a reachable SQL Server instance
- Optional: Groq/OpenAI API key for LLM access
- Optional: Qdrant if you want vector ingestion enabled
- Windows PowerShell is assumed below, since this project is set up for Windows local testing

## 2) Clone and open the project

```powershell
cd C:\Users\User\Documents\Bharat\Project\Rag
```

Check the project files:

```powershell
Get-ChildItem
```

You should see folders such as:

- api/
- ui/
- tools/
- rag/
- database/
- sample_data/
- tests/

## 3) Create a fresh virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

If you want the LLM extras too:

```powershell
pip install -e .[dev,llm]
```

## 4) Configure environment variables

Copy the example config:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and set values that match your local environment.

Recommended local config for Groq + SQL Server Express:

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
QDRANT_ENABLED=false
EMBEDDING_DIMENSION=384

SQLSERVER_DSN=
SQLSERVER_HOST=DESKTOP-CE9MBJQ\SQLEXPRESS
SQLSERVER_DATABASE=EnterpriseChatbotDemo
SQLSERVER_USER=
SQLSERVER_PASSWORD=
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_TRUSTED_CONNECTION=true
SQLSERVER_ENCRYPT=false
```

Notes:

- For `LLM_PROVIDER=mock`, no external key is required.
- If SQL Server is not configured, the app will still start but SQL features may fail.
- If your machine uses a different SQL Server host or named instance, update `SQLSERVER_HOST`.
- If you are using SQL Server Express, the value often looks like `DESKTOP-XXXX\SQLEXPRESS`.

## 5) Prepare SQL sample data

This project includes demo SQL scripts for sales or subscription analysis.

### Option A: Product sales demo

Open SQL Server Management Studio (SSMS) or Azure Data Studio and run:

```sql
:r database/create_demo_product_sales.sql
```

If `:r` does not work, open the script manually and run it.

### Option B: Subscription analysis demo

```sql
:r database/seed_subscription_analysis_demo.sql
```

Check the correct database name in `.env` before running.

## 6) Start the FastAPI backend

Open one terminal and run:

```powershell
cd C:\Users\User\Documents\Bharat\Project\Rag
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Expected result: uvicorn starts successfully without errors.

### Health checks

In a second terminal, test the app:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Or:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/config/status" | ConvertTo-Json -Depth 8
```

If the API responds, the backend is running correctly.

### SQL health check

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sql/health" | ConvertTo-Json -Depth 8
```

Check:

- `connected` should be `true` if SQL is set correctly
- `error` should be empty or not present when working

If SQL is not connected, review the SQL Server fix guide in:

- [docs/sql_server_fix.md](sql_server_fix.md)

## 7) Start the Streamlit UI

Open another terminal and run:

```powershell
cd C:\Users\User\Documents\Bharat\Project\Rag
.\.venv\Scripts\Activate.ps1
streamlit run ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Then open:

```text
http://localhost:8501
```

In the UI, you can:

- upload PDFs/docs/txt/CSV/Excel files
- click `Upload`
- click `Ingest to RAG`
- ask questions in the chat box
- check SQL diagnostics from the sidebar

## 8) Basic demo flow

### A. Simple API smoke test

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the enterprise data policy","session_id":"demo","files":[]}' | ConvertTo-Json -Depth 8
```

This is the exact demo pattern from the main project README.

### B. SQL demo query

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Show top products by revenue from SQL database","session_id":"sql-demo","files":[]}' | ConvertTo-Json -Depth 8
```

### C. RAG demo query

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the enterprise data policy and summarize access requirements","session_id":"rag-demo","files":[]}' | ConvertTo-Json -Depth 8
```

## 9) Demo queries to use during live testing

Use these queries to validate the system end-to-end.

### Basic demo queries

```text
Retrieve the enterprise data policy
Retrieve the enterprise data policy and summarize access requirements
Show top products by revenue from SQL database
Which products had the highest net revenue last quarter?
Summarize the company data access policy
```

### SQL-only queries

```text
Which products have the highest sales by category?
Show top 10 products by revenue in descending order
What are the total sales and margin by region?
Which customers generated the highest contribution margin?
List the most profitable product segments from the SQL database
```

### RAG/document queries

```text
Retrieve the enterprise data policy
Summarize the policy and explain allowed data access conditions
What are the rules for confidential information handling?
Find the retention or privacy instructions from the knowledge base
```

### PDF / file ingestion queries

```text
Summarize this PDF and explain the SLA breach definition
What does the PDF say about payment leakage?
Explain the policy terms found in the uploaded document
Identify the key clauses from the uploaded file
```

### Multi-tool routing queries

```text
Retrieve the SLA breach definition from RAG, summarize the PDF, and show complaint tickets that breached SLA from SQL
Use SQL and the knowledge base to explain the subscription churn drivers
Compare policy requirements with the file content and show related SQL records
```

## 10) Ingest the sample knowledge base

The project includes some sample docs for RAG. You can ingest them through the API:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" -Method Post -ContentType "application/json" -Body '["sample_data/policies.md"]'
```

For the subscription demo:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" -Method Post -ContentType "application/json" -Body '["sample_data/subscription_analysis_knowledge.md","output/pdf/subscription_analysis_demo.pdf"]'
```

Then test with queries such as:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the payment leakage definition from the knowledge base","session_id":"rag-test","files":[]}' | ConvertTo-Json -Depth 8
```

## 11) Run the automated project tests

From the project root:

```powershell
pytest -q
```

This project includes tests for:

- orchestrator behavior
- RAG ingestion and retrieval
- SQL safety checks
- subscription SQL templates

## 12) Typical success checks

You should confirm all of the following before calling the system demo-ready:

- API responds on `/health`
- `/config/status` shows the expected provider and database values
- `/sql/health` reports connected state correctly
- Streamlit UI opens without error
- A basic question returns a normal answer from the chat API
- A SQL question returns a structured response or SQL result
- A document/RAG question returns grounded content from uploaded or ingested files

## 13) Troubleshooting

### API does not start

Check:

```powershell
python --version
pip list
```

Then reinstall dependencies:

```powershell
pip install -e .[dev]
```

### SQL Server not connected

Review:

- [docs/sql_server_fix.md](sql_server_fix.md)
- .env values for `SQLSERVER_HOST`, `SQLSERVER_DATABASE`, `SQLSERVER_DRIVER`
- whether SQL Server service is actually running

### Streamlit cannot connect to API

Set the API URL in the sidebar to:

```text
http://localhost:8000
```

### Knowledge retrieval is empty

- Make sure Qdrant is running
- Check `QDRANT_ENABLED=true` if vector retrieval is needed
- Ingest the source file via `/ingest`

### LLM call fails

- Confirm `LLM_PROVIDER` is correctly set
- Confirm the corresponding API key is valid
- If you want a fully local test path, set `LLM_PROVIDER=mock`

## 14) Demo checklist for presentation

Before a demo, run this in order:

1. Start API
2. Start Streamlit
3. Confirm `/health`
4. Confirm `/sql/health`
5. Upload sample document or PDF
6. Click `Ingest to RAG`
7. Ask a SQL question
8. Ask a RAG/document question
9. Ask a combined multi-tool question
10. Show the API response JSON or the Streamlit side tabs

## 15) Recommended demo script

Use this short script in a live call:

```text
1. Open the app and say: "Show top products by revenue from SQL database."
2. Upload the policy or PDF and ingest it.
3. Ask: "Retrieve the enterprise data policy and summarize access requirements."
4. Ask: "Summarize this PDF and explain the SLA breach definition."
5. Ask: "Retrieve the SLA breach definition from RAG, summarize the PDF, and show complaint tickets that breached SLA from SQL."
6. Explain that the system combines SQL, document ingestion, and retrieval pipelines.
```

This gives a clean demonstration of the full enterprise AI chatbot workflow.

## 16) Quick command summary

```powershell
cd C:\Users\User\Documents\Bharat\Project\Rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
# new terminal
streamlit run ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

If you want the fastest basic trial, use the mock LLM option and first test the health endpoints before enabling SQL and document ingestion.
## Automatic Mode and live progress

1. Restart FastAPI and Streamlit after updating the code.
2. Enable **Automatic Mode** in the sidebar. Configure a live LLM provider and
   connect SQL Server; mock mode cannot investigate a real database.
3. Ask: `Show top 10 products by NetRevenue in descending order`.
4. Watch **Live Agent Progress**: table identification, column investigation,
   relationship verification, SQL generation, compilation, execution, and result
   validation should update while the request is running.
5. Verify the selected tools and their purposes, then compare the generated SQL
   against the actual schema. The answer should include SQL, up to ten returned
   rows, total returned rows, and total columns.
6. Upload a BRD and ask a database question that uses its definitions. Document
   tools should execute before SQL generation. Automatic Mode should state any
   necessary assumptions without asking clarification questions.
7. Try an unsupported calculation (for example, margin when no cost evidence
   exists). Expect an honest limitation rather than invented values or a question.
8. Disable Automatic Mode to restore clarification questions with options.

See [automatic_mode.md](automatic_mode.md) for API events, counting semantics,
permissions, token usage, and operational limitations.
