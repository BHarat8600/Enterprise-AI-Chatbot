# SQL Server Connection Fix

If the chat response contains:

```json
"notice": "SQL Server is not configured. Set SQLSERVER_DSN or host credentials."
```

then the running API process did not load `SQLSERVER_HOST`.

## Correct `.env`

```dotenv
SQLSERVER_HOST=DESKTOP-CE9MBJQ\SQLEXPRESS
SQLSERVER_DATABASE=Subscription_Analysis
SQLSERVER_USER=
SQLSERVER_PASSWORD=
SQLSERVER_DRIVER=ODBC Driver 17 for SQL Server
SQLSERVER_TRUSTED_CONNECTION=true
SQLSERVER_ENCRYPT=false
```

After changing `.env`, restart both API and Streamlit. The settings are cached at process startup.

## Check What The API Loaded

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/config/status"
```

Expected:

```text
sqlserver_host     DESKTOP-CE9MBJQ\SQLEXPRESS
sqlserver_database Subscription_Analysis
```

## Check SQL Connection

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sql/health" | ConvertTo-Json -Depth 6
```

If `connected` is `false`, inspect `error`.

Common fixes:

- SQL Server service must be running: `SQL Server (SQLEXPRESS)`.
- Install Microsoft ODBC Driver 18 for SQL Server, or set `SQLSERVER_DRIVER` to an installed driver from `/sql/health`, such as `ODBC Driver 17 for SQL Server`.
- For local SQL Express with ODBC Driver 17, use `SQLSERVER_ENCRYPT=false`.
- For SQL Express named instances, `SQLSERVER_HOST=DESKTOP-CE9MBJQ\SQLEXPRESS` is correct.
- If named instance resolution fails, enable SQL Server Browser service or use a fixed TCP port.
- The Windows account running Python must have access to `Subscription_Analysis`.

## Jupyter Notebook

Open:

```text
notebooks/sql_rag_streamlit_test.ipynb
```

Run cells top to bottom. It tests:

- `.env` settings
- installed ODBC drivers
- direct `pyodbc` connection
- schema queries
- business SQL queries
- RAG ingestion and retrieval
- orchestrator response
- FastAPI endpoints
