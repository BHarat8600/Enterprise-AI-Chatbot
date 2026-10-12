# Subscription Analysis End-to-End Testing

## Files Created

- Demo PDF: `output/pdf/subscription_analysis_demo.pdf`
- RAG knowledge document: `sample_data/subscription_analysis_knowledge.md`
- Question list: `sample_data/subscription_test_questions.md`
- Optional seed script: `database/seed_subscription_analysis_demo.sql`

## Environment

Set your SQL database:

```dotenv
SQLSERVER_HOST=DESKTOP-CE9MBJQ\SQLEXPRESS
SQLSERVER_DATABASE=Subscription_Analysis
SQLSERVER_TRUSTED_CONNECTION=true
SQLSERVER_ENCRYPT=false
```

Restart FastAPI and Streamlit after changing `.env`.

Check what the API loaded:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/config/status"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sql/health" | ConvertTo-Json -Depth 6
```

## Seed Demo Rows

Run in SSMS or Azure Data Studio:

```sql
:r database/seed_subscription_analysis_demo.sql
```

If `:r` does not work, open the SQL file and run it manually.

## Ingest RAG Sources

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" -Method Post -ContentType "application/json" -Body '["sample_data/subscription_analysis_knowledge.md","output/pdf/subscription_analysis_demo.pdf"]'
```

## Test PDF Tool

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Summarize this PDF and explain the SLA breach definition","session_id":"pdf-test","files":["output/pdf/subscription_analysis_demo.pdf"]}' | ConvertTo-Json -Depth 8
```

## Test SQL Tool

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Which subscription plans have the highest active contract value from SQL?","session_id":"sql-test","files":[]}' | ConvertTo-Json -Depth 8
```

## Test RAG Tool

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the payment leakage definition from the knowledge base","session_id":"rag-test","files":[]}' | ConvertTo-Json -Depth 8
```

## Test Multi-Tool Routing

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"query":"Retrieve the SLA breach definition from RAG, summarize the PDF, and show complaint tickets that breached SLA from SQL","session_id":"multi-tool-test","files":["output/pdf/subscription_analysis_demo.pdf"]}' | ConvertTo-Json -Depth 10
```
