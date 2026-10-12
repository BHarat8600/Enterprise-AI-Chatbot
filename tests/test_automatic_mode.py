import asyncio
import json
from types import SimpleNamespace

import pytest

from agents.database_agent import DatabaseAgent, validate_read_only
from agents.orchestrator import AgentOrchestrator
from agents.planner_agent import PlannerAgent
from agents.response_agent import ResponseGenerationAgent
from config.settings import Settings
from memory.store import ConversationMemory
from models.schemas import ChatRequest, ChatResponse, ExecutionPlan, GuardrailResult, JudgeResult, EvaluationMetrics
from rag.pipeline import RagPipeline
from services.chat_stream import chat_events
from services.progress import progress, progress_sink
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.sql_tool import SqlServerTool


class SequenceLLM:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return json.dumps(next(self.outputs))


class Database:
    settings = SimpleNamespace(sqlserver_dsn="test", sqlserver_host=None)

    def __init__(self, count=12, invalid_compile=False):
        self.calls = []
        self.count = count
        self.invalid_compile = invalid_compile
        self.executions = 0

    def validate_sql(self, sql):
        SqlServerTool(Settings()).validate_sql(sql)

    def execute_select(self, sql):
        self.calls.append(sql)
        if "INFORMATION_SCHEMA.TABLES" in sql:
            return [{"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Sales"}]
        if "INFORMATION_SCHEMA.COLUMNS" in sql:
            return [{"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Sales", "COLUMN_NAME": "Revenue", "DATA_TYPE": "decimal", "computed_definition": None}]
        if "sys.foreign_key_columns" in sql or "sys.indexes" in sql:
            return []
        if "dm_exec_describe_first_result_set" in sql:
            if self.invalid_compile:
                self.invalid_compile = False
                return [{"error_number": 207, "error_message": "Invalid column name Wrong"}]
            return [{"name": "Revenue", "system_type_name": "decimal(18,2)", "error_number": None}]
        raise AssertionError(sql)

    def execute_preview(self, sql):
        self.executions += 1
        return {"columns": ["Revenue"], "column_count": 1, "row_count": self.count,
                "rows": [{"Revenue": i} for i in range(min(10, self.count))]}


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 12])
async def test_schema_investigation_compiles_before_execution_and_reports_shape(count):
    llm = SequenceLLM([{"tables": ["dbo.Sales"]}, {"sql": "SELECT Revenue FROM dbo.Sales", "assumptions": []}])
    database = Database(count)
    events = []

    async def collect(event):
        events.append(event)

    token = progress_sink.set(collect)
    try:
        result = await DatabaseAgent(llm, database).answer("Show revenue", "", [])
    finally:
        progress_sink.reset(token)
    assert result.success
    assert result.output["row_count"] == count
    assert result.output["column_count"] == 1
    assert len(result.output["rows"]) == min(10, count)
    assert database.executions == 1
    assert "decimal" in llm.prompts[1]
    completed = [e["step"] for e in events if e["status"] == "Completed"]
    assert completed.index("Compile and validate SQL") < completed.index("Execute SQL")
    assert events[0]["status"] == "Pending"


@pytest.mark.asyncio
async def test_sql_compilation_failure_repairs_once_before_execution():
    database = Database(invalid_compile=True)
    llm = SequenceLLM([{"tables": ["dbo.Sales"]}, {"sql": "SELECT Wrong FROM dbo.Sales"}, {"sql": "SELECT Revenue FROM dbo.Sales"}])
    result = await DatabaseAgent(llm, database).answer("Show revenue", "", [])
    assert result.success
    assert database.executions == 1
    assert "Invalid column name Wrong" in llm.prompts[-1]


@pytest.mark.asyncio
async def test_hallucinated_table_never_executes():
    database = Database()
    result = await DatabaseAgent(SequenceLLM([{"tables": ["dbo.Invented"]}]), database).answer("Revenue", "", [])
    assert not result.success
    assert database.executions == 0


@pytest.mark.parametrize("sql", ["SELECT * INTO dbo.Copy FROM dbo.Sales", "DELETE FROM dbo.Sales", "SELECT 1; SELECT 2", "SELECT * FROM OPENROWSET('a','b','c')", "SELECT NEXT VALUE FOR dbo.Sequence"])
def test_generated_sql_blocks_mutation_and_external_access(sql):
    with pytest.raises(ValueError):
        validate_read_only(sql, SqlServerTool(Settings()))


@pytest.mark.asyncio
async def test_automatic_mode_suppresses_planner_and_response_questions():
    question = {"question": "Which column?", "options": ["A", "B"]}
    llm = SequenceLLM([{"tools": ["direct"], "clarification_questions": [question]},
                       {"answer": "Choose a column?", "confidence": 0.5, "clarification_questions": [question]}])
    plan = await PlannerAgent(llm).plan("Request", [], automatic_mode=True)
    assert not plan.clarification_questions
    result = await ResponseGenerationAgent(llm).assess("Request", plan, [], "", automatic_mode=True)
    assert not result["clarification_questions"]
    assert not result["clarification_options"]
    assert result["status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_automatic_final_answer_contains_exact_sql_preview_and_counts():
    settings = Settings(llm_provider="mock", qdrant_enabled=False)
    database = Database()
    llm = SequenceLLM([{"tools": ["sql"]}, {"tables": ["dbo.Sales"]},
        {"sql": "SELECT Revenue FROM dbo.Sales", "assumptions": []},
        {"answer": "Revenue results verified.", "confidence": 0.95, "clarification_questions": []}])
    orchestrator = AgentOrchestrator(llm, ConversationMemory(), database, PdfTool(), DocumentTool(), RagPipeline(settings))
    result = await orchestrator.chat(ChatRequest(query="Show revenue", automatic_mode=True))
    assert result.status == "answered"
    assert "SELECT Revenue FROM dbo.Sales" in result.answer
    assert "Total rows: 12" in result.answer and "Total columns: 1" in result.answer
    assert result.metrics.llm_calls == 4
    assert not result.clarification_questions


@pytest.mark.asyncio
async def test_progress_arrives_before_request_finishes():
    release = asyncio.Event()

    class Orchestrator:
        async def chat(self, payload):
            await progress("Investigate", "In Progress")
            await release.wait()
            return ChatResponse(answer="Done", session_id=payload.session_id, plan=ExecutionPlan(intent="test"),
                tool_results=[], citations=[], guardrails=GuardrailResult(allowed=True), judge=JudgeResult(),
                metrics=EvaluationMetrics(), timeline=[])

    stream = chat_events(Orchestrator(), ChatRequest(query="test"))
    first = json.loads(await asyncio.wait_for(anext(stream), 1))
    assert first["type"] == "progress" and not release.is_set()
    release.set()
    last = json.loads(await anext(stream))
    assert last["type"] == "result"
    await stream.aclose()
