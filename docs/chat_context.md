Chat context and clarification
==============================

Use New Chat in the sidebar to start with a new random session ID, empty
conversation, and empty upload selection. API clients should use a unique
session_id for each chat (omitting it generates a new ID for each request).
Continue a conversation by reusing its ID, including clarification replies.

History selection ranks whole turns locally by word overlap, retaining older
relevant turns within a 6,000-character budget. The latest turn is eligible for
follow-up references. This is lexical retrieval, not semantic retrieval; it can
miss paraphrases. History and pending clarifications are process-local and are
lost on restart. Production multi-worker deployments need a shared store and
authenticated session ownership; session IDs alone are not access control.

The planner and response step ask only about concrete ambiguity that changes
the answer. Supplied BRD files are read before deciding they are ambiguous.
Clear requirements do not trigger questions solely because confidence is low.
Low confidence without an identified ambiguity returns insufficient_evidence.
Replies needing clarification use status=needs_clarification,
clarification_questions, and clarification_options (question plus options).
The UI offers radio choices and an optional custom answer. Open questions are
reserved for cases without meaningful evidence-based choices. Replies continue
the unresolved request in the same chat. Confidence is not a guarantee of
correctness. Malformed model output and service failures return status=error
with a retry message rather than a requirement clarification.

SQL output includes the database column schema when SQL Server is configured,
so column choices can refer to actual names. SQL generation still uses fixed
templates rather than arbitrary LLM-generated SQL. Unsupported margin/profit
requests report that limitation instead of running an unrelated query. The
product template uses NetRevenue when net revenue is explicitly selected.

Token metrics cover planner and response LLM calls in one request. Provider
counts are preferred; absent counts use character estimates and set
tokens_estimated=true. Model-free history ranking and combining answer drafting
with evidence assessment reduce calls without truncating tool evidence.
Existing retrieval and judge quality metrics remain heuristics, as disclosed
by Metrics Details; they must not be interpreted as measured accuracy.

POST /ingest?session_id=... ingests chat uploads into a local session index,
without writing into the shared Qdrant collection. Ingestion without session_id
continues to populate the shared enterprise knowledge base, intentionally
available to all chats. The UI uses scoped ingestion. SQL data and the shared
enterprise knowledge base remain shared sources, not conversation history.
