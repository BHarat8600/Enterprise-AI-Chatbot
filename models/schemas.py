from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolName(str, Enum):
    sql = "sql"
    pdf = "pdf"
    document = "document"
    rag = "rag"
    direct = "direct"


class AgentName(str, Enum):
    router = "router"
    planner = "planner"
    tool_selector = "tool_selector"
    sql = "sql"
    pdf = "pdf"
    document = "document"
    rag = "rag"
    response = "response"
    validation = "validation"
    judge = "judge"
    guardrail = "guardrail"
    monitoring = "monitoring"


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceCitation(BaseModel):
    source_id: str
    title: str
    location: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    tool: ToolName
    reason: str
    args: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    clarification_options: list[dict[str, Any]] = Field(default_factory=list)
    intent: str
    can_answer_directly: bool = False
    steps: list[ToolCall] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    tool: ToolName
    success: bool
    output: Any
    latency_ms: float
    citations: list[SourceCitation] = Field(default_factory=list)
    error: str | None = None


class GuardrailResult(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    masked_text: str | None = None


class JudgeResult(BaseModel):
    correctness: float = 0.0
    groundedness: float = 0.0
    faithfulness: float = 0.0
    completeness: float = 0.0
    relevance: float = 0.0
    hallucination_score: float = 0.0
    notes: str = ""


class EvaluationMetrics(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    tokens_estimated: bool = False
    context_precision: float = 0.0
    context_recall: float = 0.0
    answer_relevancy: float = 0.0
    faithfulness: float = 0.0
    groundedness: float = 0.0
    response_similarity: float = 0.0
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    latency_ms: float = 0.0
    tool_success_rate: float = 0.0


class ChatRequest(BaseModel):
    automatic_mode: bool = False
    query: str
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    clarification_options: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "answered"
    clarification_questions: list[str] = Field(default_factory=list)
    answer: str
    session_id: str
    plan: ExecutionPlan
    tool_results: list[ToolResult]
    citations: list[SourceCitation]
    guardrails: GuardrailResult
    judge: JudgeResult
    metrics: EvaluationMetrics
    timeline: list[dict[str, Any]]
