# Architecture

## System Architecture

```mermaid
flowchart LR
    User --> UI[Streamlit UI]
    UI --> API[FastAPI Backend]
    API --> Guardrail[Guardrail Agent]
    Guardrail --> Planner[Planner Agent]
    Planner --> ToolSelector[Tool Selection]
    ToolSelector --> SQL[SQL Server Tool]
    ToolSelector --> PDF[PDF Tool]
    ToolSelector --> DOC[Document Tool]
    ToolSelector --> RAG[Hybrid RAG Tool]
    RAG --> Qdrant[(Qdrant)]
    RAG --> BM25[(Sparse Index)]
    SQL --> Response[Response Generation Agent]
    PDF --> Response
    DOC --> Response
    RAG --> Response
    Response --> Validation[Validation Agent]
    Validation --> Judge[LLM Judge]
    Judge --> Observability[OpenTelemetry / Prometheus / Langfuse]
    Judge --> API
```

## Multi-Agent Responsibilities

- Router Agent: derives the initial intent.
- Planner Agent: creates a tool execution plan.
- Tool Selection Agent: maps planned steps to concrete tools.
- SQL Agent: validates and executes safe SQL Server `SELECT` queries.
- PDF Agent: extracts text and summarizes PDF content, with OCR extension points.
- Document Agent: reads TXT, Markdown, DOCX, CSV, and Excel files.
- RAG Agent: performs ingestion, chunking, sparse retrieval, and vector-database integration.
- Response Generation Agent: synthesizes the final grounded answer.
- Validation Agent: checks tool outputs for failures and empty evidence.
- LLM Judge Agent: scores correctness, groundedness, faithfulness, completeness, relevance, and hallucination risk.
- Guardrail Agent: blocks injection attempts, masks PII, and validates outputs.
- Monitoring Agent: emits logs, metrics, traces, and evaluation results.

## Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant G as Guardrail
    participant P as Planner
    participant T as Tools
    participant R as Response Agent
    participant J as Judge
    U->>API: Chat query + files
    API->>G: Validate and mask input
    G->>P: Safe query
    P->>API: Execution plan
    API->>T: Execute selected tools
    T->>API: Tool results + citations
    API->>R: Build grounded answer
    R->>J: Evaluate response
    J->>API: Scores and metrics
    API->>U: Answer, citations, timeline
```

