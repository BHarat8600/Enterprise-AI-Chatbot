import json

import pytest

from agents.orchestrator import AgentOrchestrator
from agents.planner_agent import PlannerAgent
from agents.response_agent import ResponseGenerationAgent
from config.settings import Settings
from memory.store import ConversationMemory
from models.schemas import ChatRequest, ExecutionPlan
from rag.pipeline import RagPipeline
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.sql_tool import SqlServerTool


class Client:
    def __init__(self, output):
        self.output = output

    async def generate(self, prompt, **kwargs):
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ['[]', 'null', '{"tools":["unknown"]}', '{"tools":42}', '```json\n{"tools":["sql"]}\n```'])
async def test_planner_handles_unexpected_model_json(raw):
    plan = await PlannerAgent(Client(raw)).plan("Show product sales", [])
    assert plan.steps[0].tool.value == "sql"


@pytest.mark.asyncio
async def test_clear_brd_answers_without_clarification():
    result = await ResponseGenerationAgent(Client(json.dumps({
        "answer": "Use NetRevenue as specified by the BRD.", "confidence": 0.97,
        "clarification_questions": [],
    }))).assess("Which revenue column?", ExecutionPlan(intent="answer"), [], "BRD specifies NetRevenue")
    assert result["status"] == "answered"
    assert not result["clarification_questions"]


@pytest.mark.asyncio
async def test_conflicting_definitions_offer_options():
    options = ["NetRevenue (after discount)", "Quantity * UnitPrice (before discount)"]
    result = await ResponseGenerationAgent(Client(json.dumps({
        "answer": "", "confidence": 0.6,
        "clarification_questions": [{"question": "Which sales definition should apply?", "options": options}],
    }))).assess("Rank sales", ExecutionPlan(intent="answer"), [], "")
    assert result["status"] == "needs_clarification"
    assert result["clarification_options"][0]["options"] == options
    assert all(option in result["answer"] for option in options)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ['null', '[]', '{"confidence":"invalid"}', 'not json'])
async def test_invalid_assessment_is_technical_error(raw):
    result = await ResponseGenerationAgent(Client(raw)).assess("Clear request", ExecutionPlan(intent="answer"), [], "")
    assert result["status"] == "error"
    assert not result["clarification_questions"]


@pytest.mark.asyncio
async def test_service_failure_returns_safe_response_and_keeps_chat():
    settings = Settings(llm_provider="mock", qdrant_enabled=False)
    memory = ConversationMemory()
    orchestrator = AgentOrchestrator(Client(RuntimeError("private provider details")), memory,
        SqlServerTool(settings), PdfTool(), DocumentTool(), RagPipeline(settings))
    response = await orchestrator.chat(ChatRequest(query="Show sales", session_id="same-chat"))
    assert response.status == "error"
    assert response.session_id == "same-chat"
    assert "private provider details" not in response.answer
    assert not response.clarification_questions


def test_sql_does_not_treat_word_selection_as_raw_sql():
    sql = SqlServerTool(Settings()).generate_sql("Show product selection by revenue")
    assert sql.startswith("SELECT TOP 10")


def test_net_revenue_option_changes_executed_column():
    sql = SqlServerTool(Settings()).generate_sql("Show top products by NetRevenue after discount")
    assert "SUM(NetRevenue)" in sql
