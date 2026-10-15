# Deep SQL Automatic Mode

Enable **Deep SQL Automatic Mode** in the sidebar for an independent SQL
investigation loop. This is separate from the existing Automatic Mode and manual
workflow; enabling either automatic control switches off the other. The API flag
is `deep_sql_automatic_mode=true`; if both flags are supplied, deep mode takes
precedence. The selected SQL Server or PostgreSQL connection applies as usual.

The dedicated `DeepSqlAgent` reads source documents first, then:

1. Reads the actual table catalog and selects relevant tables, including bridge
   tables when needed.
2. Inspects columns, data types, computed definitions, foreign keys and unique
   keys. Additional tables can be inspected in subsequent rounds.
3. Requests distinct values for relevant ambiguous categorical filters such as
   status, category, color, flags and enum/integer codes. Probes are restricted to
   verified columns. If more evidence is needed, it can submit read-only
   diagnostic SQL for counts, ranges, null rates, join checks or small samples.
4. Sends those stored values to the LLM to resolve the intended predicates. For
   example, a request for “active” records can use an actual stored label such as
   `Active`, instead of assuming the database contains `active` or `Enabled`.
5. Generates read-only SQL and checks filter declarations against the retrieved
   values. Ordinary textual equality/IN predicates are also checked for undeclared
   or inconsistent literals. The database compiles/verifies output metadata.
6. Reviews the candidate against requirements, types, relationships and category
   evidence. The loop may fetch more evidence or revise SQL; new evidence
   invalidates the prior candidate. A query is released only after compilation
   and a separate model goal review pass.
7. Tries alternative approaches after failed validation, repeated steps or a
   premature stop. If evidence cannot settle a business interpretation, it asks
   1-3 focused questions with alternative choices. Open questions are reserved
   for cases without meaningful options. The original request remains pending
   in that chat; answering the questions resumes investigation with fresh checks.

The goal here is a verified SQL draft. Deep mode always waits for **Execute** for
the final query, even if an API client omits `defer_database_execution`. Execute
still bypasses the LLM, shows five rows and offers the full CSV report. Distinct
value probes and bounded diagnostic samples are deliberate exceptions to keeping result data out of the
model; final query/report rows are never fed back by this workflow.

## Token use and stopping

Deep investigation steps now show a short operational question, the action's
evidence outcome, elapsed seconds and token usage. Column discovery, data-type
verification and relationship verification have separate rows. These are
observable task summaries, not private model reasoning transcripts.

`DEEP_SQL_STEP_SECONDS=15` is the minimum visibility duration for a deep step.
`DEEP_SQL_LARGE_STEP_SECONDS=30` applies when step input plus output usage reaches
`DEEP_SQL_LARGE_TOKEN_THRESHOLD=4000`. The UI updates the elapsed-time countdown
while waiting. Time already spent on real work counts toward the duration; a
40-second operation does not receive an additional 15/30-second delay. Nested
round and tool-step durations overlap. Preliminary pipeline bookkeeping is not
artificially delayed. Pacing adds no model calls or tokens, and does not by itself
improve correctness. Set durations to zero to disable display pacing.

Transient service failures retry within the investigation budget up to three
failed service calls. HTTP status is displayed when available; authentication
failures stop with an actionable status instead of endless retries. Detailed
exceptions remain in server logs; credentials and raw provider error bodies are
not displayed in progress.

Relevant schema and distinct profiles are cached within each request. Duplicate
probes do not repeat database work. Prompts contain compact current evidence,
not a growing transcript of every step or long model reasoning. No ordinary
planner or final response-generation call is needed for the deep SQL path. Token
metrics cover every investigation round. Clear requests can finish without any
distinct-value probe.

`DEEP_SQL_MAX_ROUNDS` defaults to 20 (range 2–60); an existing `.env` override
still takes precedence. Repeated actions trigger alternative-strategy feedback
rather than immediate termination. Three repeated stalls, a repeated stop or
the round limit allow one extra compact clarification-generation call when
verified schema exists. If no answerable business ambiguity is identified,
the agent reports the limitation. Technical outages are not converted into
arbitrary requirement questions. Increasing the limit cannot guarantee an
answer when business definitions or accessible evidence are missing.

Diagnostic queries are compiled and checked as read-only, return at most five
rows and twelve columns, and are cached per request (up to six distinct probes).
Long cells and output beyond the small text budget are explicitly marked omitted;
samples are not treated as exhaustive results. Final report rows are not requested
or exported during investigation. This keeps evidence collection separate from
the Execute workflow and limits token growth. Model calls including the optional
clarification fallback are included in request token metrics.

`DEEP_SQL_DISTINCT_LIMIT` defaults to 50 (range 5–200). Each lookup fetches at most
that many values plus one to detect truncation. A capped list is explicitly marked
incomplete; missing values cannot be assumed absent. The agent can perform a
targeted, case-insensitive literal substring search in further rounds. Long
values are explicitly omitted instead of silently shortened into invalid filter
literals. Requirements that need an exhaustive category list require a complete,
unsearched profile; simple exclusion of verified labels does not. If these
constraints prevent resolving a condition, the agent investigates alternatives
or asks for the unresolved business interpretation. Profiles support categorical
text, booleans, enums and numeric codes. Decimal codes preserve precision, and
filter validation follows column types (including boolean flags represented as
SQL 1/0). Text labels remain exact. Avoid profiling arbitrary free-text, arrays,
JSON and continuous measures; use concise diagnostic aggregates when needed.

Live progress shows each round, metadata investigation, distinct probes, SQL
diagnostics, validation, recovery, clarification and final goal review. Complex SQL expression semantics and business
interpretations still rely on model review; compilation and value checks are not
a mathematical guarantee of correctness. Automated tests cover both dialects
with controlled metadata and values; live database behavior remains unverified.

## Evaluating the 99% target

99% is a desired measured success rate, not a confidence threshold or a guarantee
provided by model self-review. Evaluate a representative held-out set of your
BRDs and questions against reviewed expected SQL and results on the real database.
Count incorrect and unresolved requests as failures, and report both first-pass
success and success after clarification. Passing unit tests checks workflow
behavior; it does not establish a 99% live answer accuracy rate.
