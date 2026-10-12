Automatic Mode
==============

Enable Automatic Mode in the Streamlit sidebar. It applies to the next message
and remains enabled until switched off. Manual mode keeps option-based
clarification. Automatic mode never returns clarification questions; unresolved
evidence produces an explicit limitation instead of an invented answer.

For database requests the agent reads the SQL Server table catalog, selects
relevant tables, inspects their columns/types/computed expressions, and checks
foreign keys and unique keys. Source documents run before SQL generation.
The LLM generates a query from that metadata rather than the existing fixed
templates. Read-only checks run before SQL Server compiles the query using
sys.dm_exec_describe_first_result_set. A failed SQL validation/execution allows
one repair using the actual error and verified schema, then stops safely.
The application executes the query once successfully, counts the returned rows
in batches, retains the first ten, and verifies the result columns against the
compiled metadata. Final evidence assessment checks request alignment; execution
success alone does not establish semantic accuracy. Defensible assumptions are
reported. Missing business definitions cannot be guaranteed from schema alone.

The final answer and SQL tab show the exact executed script, first ten rows,
total returned row count, and column count (including zero-row result sets).
For TOP/filtered queries, row count describes that query's result, not the total
underlying table. Preview order follows the generated SQL; without ORDER BY,
the first ten rows have no guaranteed ordering. Failed queries have no fabricated
counts or results.

Both modes use POST /chat/stream for live newline-delimited JSON events:
progress events contain step, status (Pending, In Progress, Completed, Failed),
and detail; tool selection includes tools with purposes and tool_mode. A result
event contains the normal ChatResponse. Heartbeats keep long operations alive.
POST /chat remains compatible. Both accept automatic_mode (default false).
Cancellation stops the asynchronous workflow; SQL already running in a worker
thread may continue until its database timeout. Configure proxies to disable
response buffering for streaming. Progress summaries describe observable work,
not private model reasoning.

Token use is reduced by selecting tables from names first, sending only selected
column metadata, using local history selection, retaining only ten result rows,
and bounding repair to one attempt. Normal automatic SQL flow uses four model
calls: tool planning, table selection, SQL generation, and evidence assessment.
Provider-reported usage is accumulated across these calls and any repair.

SQL Server must be configured and reachable. Use a database principal with only
the required SELECT and metadata permissions; application query checks supplement
database permissions. Automatic Mode does not run DDL or data modifications.
Mock mode cannot generate verified live SQL. Automated tests use fake database
metadata and execution results; validate your own SQL Server schema and BRDs
before relying on answers in production.
