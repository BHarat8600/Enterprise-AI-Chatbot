# Database connections and query executor

The sidebar supports SQL Server and PostgreSQL. **Use .env defaults** is enabled
initially. The API supplies non-secret defaults to the settings controls; passwords
are never returned by that endpoint or prefilled in the browser. Uncheck the box
to override host, database, authentication, username/password, driver or TLS
settings, then use **Test connection**. SQL Server supports integrated Windows
authentication (the API process identity), username/password, and configured ODBC
DSNs. PostgreSQL supports username/password, port and SSL mode.

Overrides apply only to that request and do not rewrite `.env` or shared settings.
A blank password uses the `.env` password only when the connection identity is
unchanged. For a different server, database, port, DSN or username, enter the
appropriate password. Changing connection settings after generating SQL requires
generating a fresh query; the executor binds a draft to its original settings.

## Generate, optionally revise, and execute

1. Choose the database engine and connection settings.
2. Ask a database question. Schema investigation identifies relevant tables,
   columns/types, computed expressions, and foreign/unique keys. SQL generation
   uses the selected engine's dialect and checks the query against the server.
3. Open the **SQL** tab. Review the generated query in the editable SQL field.
4. Optionally edit SQL directly, or describe logic/column changes in **Optional
   changes to logic or columns** and click **Update query**. Model-assisted changes
   repeat schema investigation. Only SQL and requested changes are forwarded;
   previously executed result rows are excluded.
5. Click **Execute**. This calls a dedicated endpoint without the planner,
   response agent, judge, or any LLM. It validates read-only SQL, runs the query,
   shows the first five rows and exact returned row/column counts, and writes all
   returned rows to CSV during that same execution. Execution consumes zero LLM
   tokens. Generated-query work still has token metrics in the Metrics tab.
6. Click **Download all report (CSV)**. The report contains all rows produced by
   that SQL, including any requested LIMIT/TOP/filter. Preview size does not limit
   the export. An empty result exports column headers. Decimal preview values are
   serialized as strings to preserve precision; CSV preserves decimal text.

The Streamlit chat sends `defer_database_execution=true`: generated data queries
are not executed until Execute is clicked and results are never added to chat
history or sent to an LLM. Schema metadata is sent to the model for generation.
Normal generation uses three model calls (plan, table selection, SQL generation),
with at most one SQL validation repair. Automatic Mode suppresses clarification;
manual mode retains clarification for unresolved ambiguity.

**Deep SQL Automatic Mode** is a separate optional workflow that investigates
categorical filter values and bounded diagnostic samples in a loop. Only this
mode deliberately sends that investigation data to the model; final query
results still stay outside chat. Unresolved business choices can now trigger
questions with alternative options; replies resume the same request.
See [deep_sql_mode.md](deep_sql_mode.md) for evidence checks and loop limits.

## PostgreSQL setup

The PostgreSQL driver is included in `pyproject.toml`. Update dependencies with
`python -m pip install -e .` using the project's virtual environment. The driver
was also installed in this workspace's `.venv` during implementation.

Optional `.env` defaults (the template includes these):

```dotenv
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=your_database
POSTGRESQL_USER=your_readonly_user
POSTGRESQL_PASSWORD=your_password
POSTGRESQL_SSLMODE=prefer
```

PostgreSQL inspection uses `information_schema` and `pg_catalog`; composite foreign
key column order is retained. Queries are checked with EXPLAIN without ANALYZE
and a zero-row wrapper for output metadata. Connections default to read-only
transactions and a 60-second statement timeout. SQL Server uses its metadata
catalog and `sys.dm_exec_describe_first_result_set`. Use database accounts with
the necessary SELECT and metadata permissions. Application SQL checks are an
additional restriction; they do not replace database permissions.

CSV files live under ignored `output/reports/`. Downloads are scoped to the chat
session and random report ID, expire after one hour, and are process-local.
Expiration is cleaned up lazily while the server runs. After an API restart,
previous report links stop working, and old files may remain on disk for local
cleanup. A shared store and authenticated ownership are needed for multi-worker
or public deployments; session IDs are not user authentication. Live SQL Server
and PostgreSQL connectivity has not been tested as part of the automated suite.
