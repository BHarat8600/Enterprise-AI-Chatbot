import pytest

from agents.deep_sql_agent import DeepSqlAgent
from agents.orchestrator import AgentOrchestrator
from config.settings import Settings
from memory.store import ConversationMemory
from models.schemas import ChatRequest
from rag.pipeline import RagPipeline
from services.deep_sql_inspection import DeepSqlInspection
from services.progress import progress_sink
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from test_automatic_mode import SequenceLLM


INSPECT = {"action": "inspect_tables", "tables": ["dbo.Sales"]}
PROFILE = {
    "action": "distinct_values",
    "columns": [{"schema": "dbo", "table": "Sales", "column": "Status"}],
}
FINISH = {
    "action": "finish",
    "goal_achieved": True,
    "checks": {k: True for k in ["requirements", "types", "relationships", "categorical_values"]},
}


def sql_action(value="Active"):
    return {
        "action": "generate_sql",
        "sql": f"SELECT Status FROM dbo.Sales WHERE Status = '{value}'",
        "filters": [{"schema": "dbo", "table": "Sales", "column": "Status", "values": [value]}],
        "validation": "Stored status matches active records",
        "assumptions": [],
    }


class Inspection:
    pg = False

    def __init__(self, compile_error=False):
        self.probes, self.compiles, self.inspections = [], [], []
        self.compile_error = compile_error

    def tables(self):
        return [
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Sales"},
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Lookup"},
        ]

    def inspect(self, tables):
        self.inspections.append(tables)
        return {
            "columns": [
                {
                    "TABLE_SCHEMA": t["TABLE_SCHEMA"],
                    "TABLE_NAME": t["TABLE_NAME"],
                    "COLUMN_NAME": "Status",
                    "DATA_TYPE": "varchar",
                }
                for t in tables
            ],
            "relationships": [],
            "unique_keys": [],
        }

    def distinct(self, column, search):
        self.probes.append((column["COLUMN_NAME"], search))
        return {
            "schema": column["TABLE_SCHEMA"],
            "table": column["TABLE_NAME"],
            "column": column["COLUMN_NAME"],
            "search": search,
            "values": ["Active", "Inactive"],
            "truncated": False,
            "omitted_long_values": 0,
        }

    def compile(self, sql):
        self.compiles.append(sql)
        if self.compile_error:
            self.compile_error = False
            raise RuntimeError("Invalid column expression")
        return ["Status"]


def agent(outputs, max_rounds=12, compile_error=False):
    llm = SequenceLLM(outputs)
    instance = DeepSqlAgent(llm, object(), max_rounds=max_rounds)
    instance.inspection = Inspection(compile_error)
    return instance, llm


@pytest.mark.asyncio
async def test_deep_loop_reads_values_before_generating_and_reviewing_sql():
    instance, llm = agent([INSPECT, PROFILE, sql_action(), FINISH])
    events = []

    async def collect(event):
        events.append(event)

    token = progress_sink.set(collect)
    try:
        result = await instance.answer("Show active sales", "", [])
    finally:
        progress_sink.reset(token)
    assert result.success and result.output["goal_achieved"]
    assert result.output["ready_to_execute"]
    assert result.output["rounds"] == 4
    assert instance.inspection.probes == [("Status", None)]
    assert "Active" in llm.prompts[2] and "Inactive" in llm.prompts[2]
    assert "compiled_candidate" in llm.prompts[-1]
    assert any("distinct" in e["step"] and e["status"] == "Completed" for e in events)
    assert not any(e["step"] == "Execute SQL" for e in events)


@pytest.mark.asyncio
async def test_no_ambiguity_needs_no_distinct_call():
    instance, llm = agent(
        [
            INSPECT,
            {"action": "generate_sql", "sql": "SELECT Status FROM dbo.Sales", "filters": []},
            FINISH,
        ]
    )
    result = await instance.answer("List all sale statuses", "", [])
    assert result.output["ready_to_execute"]
    assert not instance.inspection.probes
    assert len(llm.prompts) == 3


@pytest.mark.asyncio
async def test_distinct_cache_prevents_duplicate_database_reads():
    instance, _ = agent([INSPECT, PROFILE, PROFILE, sql_action(), FINISH])
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]
    assert len(instance.inspection.probes) == 1


@pytest.mark.asyncio
async def test_unknown_column_probe_is_rejected_without_database_read():
    bad = {
        "action": "distinct_values",
        "columns": [{"schema": "dbo", "table": "Sales", "column": "Invented"}],
    }
    instance, llm = agent([INSPECT, bad, PROFILE, sql_action(), FINISH])
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]
    assert instance.inspection.probes == [("Status", None)]
    assert "verified columns" in llm.prompts[2]


@pytest.mark.asyncio
async def test_compile_error_is_used_to_repair_in_loop():
    instance, llm = agent(
        [
            INSPECT,
            PROFILE,
            sql_action(),
            {**sql_action(), "validation": "Corrected expression"},
            FINISH,
        ],
        compile_error=True,
    )
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]
    assert len(instance.inspection.compiles) == 2
    assert "Invalid column expression" in llm.prompts[3]


@pytest.mark.asyncio
async def test_unverified_value_cannot_be_released():
    instance, _ = agent([INSPECT, PROFILE, sql_action("MadeUp"), FINISH], max_rounds=4)
    result = await instance.answer("Show active sales", "", [])
    assert not result.output["ready_to_execute"]
    assert not result.output["goal_achieved"]
    assert not instance.inspection.compiles


@pytest.mark.asyncio
async def test_bounded_loop_never_publishes_unverified_candidate():
    instance, _ = agent([INSPECT, PROFILE, sql_action()], max_rounds=3)
    result = await instance.answer("Show active sales", "", [])
    assert result.output["goal_achieved"] is False
    assert result.output["ready_to_execute"] is False
    assert "limit" in result.output["limitation"]
    assert "sql" not in result.output


@pytest.mark.parametrize(
    "sql,filters",
    [
        ("SELECT Status FROM dbo.Sales WHERE Status='Active'", []),
        ("SELECT Status FROM dbo.Sales WHERE Status IN ('Active')", []),
        ("SELECT Status FROM dbo.Sales WHERE Status='Invented'", sql_action()["filters"]),
    ],
)
def test_ordinary_categorical_sql_predicates_require_truthful_evidence(sql, filters):
    schema = Inspection().inspect([{"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Sales"}])
    with pytest.raises(ValueError):
        DeepSqlAgent._check_declared_predicates(sql, filters, schema)


@pytest.mark.asyncio
async def test_more_evidence_invalidates_compiled_query_until_regenerated():
    more = {"action": "inspect_tables", "tables": ["dbo.Lookup"]}
    instance, _ = agent([INSPECT, PROFILE, sql_action(), more, FINISH], max_rounds=5)
    result = await instance.answer("Show active sales", "", [])
    assert not result.output["ready_to_execute"]


@pytest.mark.asyncio
async def test_orchestrator_deep_mode_bypasses_existing_agents_and_never_executes(monkeypatch):
    import agents.orchestrator as module

    instance, llm = agent([INSPECT, PROFILE, sql_action(), FINISH])

    def factory(metered, *args, **kwargs):
        instance.llm = metered
        return instance

    monkeypatch.setattr(module, "DeepSqlAgent", factory)
    settings = Settings(_env_file=None, llm_provider="mock", qdrant_enabled=False)
    orchestrator = AgentOrchestrator(
        llm, ConversationMemory(), object(), PdfTool(), DocumentTool(), RagPipeline(settings)
    )

    async def forbidden(*args, **kwargs):
        raise AssertionError("Existing planner/automatic SQL agent must not run in deep mode")

    monkeypatch.setattr(orchestrator.planner, "plan", forbidden)
    monkeypatch.setattr(orchestrator.database_agent, "answer", forbidden)
    monkeypatch.setattr(orchestrator.response_agent, "assess", forbidden)
    result = await orchestrator.chat(
        ChatRequest(query="Show active sales", deep_sql_automatic_mode=True)
    )
    assert result.status == "query_ready"
    assert result.plan.intent == "deep_sql_investigation"
    assert not result.clarification_questions
    assert result.metrics.llm_calls == 4


@pytest.mark.asyncio
async def test_truncated_profile_triggers_targeted_search_before_accepting_value():
    targeted = {
        "action": "distinct_values",
        "columns": [{"schema": "dbo", "table": "Sales", "column": "Status", "search": "act"}],
    }
    instance, llm = agent([INSPECT, PROFILE, sql_action(), targeted, sql_action(), FINISH])

    def distinct(column, search):
        instance.inspection.probes.append(search)
        return {
            "schema": "dbo",
            "table": "Sales",
            "column": "Status",
            "search": search,
            "values": ["Active"] if search else ["Archived"],
            "truncated": search is None,
            "omitted_long_values": 0,
        }

    instance.inspection.distinct = distinct
    result = await instance.answer("Show active sales", "", [])
    assert result.output["goal_achieved"]
    assert instance.inspection.probes == [None, "act"]
    assert len(instance.inspection.compiles) == 1
    assert "not verified" in llm.prompts[3]


def test_complete_set_filter_cannot_use_truncated_or_targeted_profiles():
    schema = Inspection().inspect([{"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Sales"}])
    filters = sql_action()["filters"]
    filters[0]["complete_set_required"] = True
    profiles = {
        "one": {
            "schema": "dbo",
            "table": "Sales",
            "column": "Status",
            "search": None,
            "values": ["Active"],
            "truncated": True,
            "omitted_long_values": 0,
        }
    }
    with pytest.raises(ValueError, match="complete unsearched"):
        DeepSqlAgent._verify_filters(filters, profiles, schema)


def test_long_labels_are_omitted_explicitly_instead_of_silently_truncated():
    class Tool:
        def execute_select(self, sql):
            return [{"value": "a" * 1000}]

    column = {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "Sales",
        "COLUMN_NAME": "Status",
        "DATA_TYPE": "varchar",
    }
    result = DeepSqlInspection(Tool()).distinct(column)
    assert result["values"] == []
    assert result["omitted_long_values"] == 1


@pytest.mark.parametrize("pg", [False, True])
def test_distinct_probe_quotes_names_limits_values_and_preserves_nulls(pg):
    class Tool:
        dialect = "PostgreSQL" if pg else "SQL Server"

        def execute_select(self, sql):
            self.sql = sql
            return [{"value": None}, {"value": "Active"}, {"value": "Inactive"}]

    tool = Tool()
    inspection = DeepSqlInspection(tool, distinct_limit=2)
    column = {
        "TABLE_SCHEMA": "public" if pg else "dbo",
        "TABLE_NAME": "Sales",
        "COLUMN_NAME": "Status",
        "DATA_TYPE": "varchar",
    }
    profile = inspection.distinct(column, "act%'_")
    assert profile["values"] == [None, "Active"]
    assert profile["truncated"]
    assert "~%''~_" in tool.sql
    assert ("LIMIT 3" if pg else "TOP 3") in tool.sql
    assert ('"Status"' if pg else "[Status]") in tool.sql


CLARIFY = {
    "action": "clarify",
    "clarification_questions": [
        {
            "question": "Which status counts as active for this report?",
            "options": ["Active only", "Active and Inactive"],
        },
        {
            "question": "Which reporting scope should apply?",
            "options": ["All available dates", "Current reporting period"],
        },
    ],
}


@pytest.mark.asyncio
async def test_deep_mode_asks_multiple_focused_questions_after_investigation():
    instance, _ = agent([INSPECT, PROFILE, CLARIFY])
    result = await instance.answer("Show qualifying sales", "", [])
    assert result.success and not result.output["ready_to_execute"]
    assert len(result.output["clarification_questions"]) == 2
    assert all(len(q["options"]) == 2 for q in result.output["clarification_options"])
    assert instance.inspection.probes


@pytest.mark.asyncio
async def test_repeated_step_recovers_instead_of_stopping_immediately():
    instance, llm = agent([INSPECT, INSPECT, INSPECT, PROFILE, sql_action(), FINISH])
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]
    assert "Try another" in llm.prompts[3]
    assert len(instance.inspection.inspections) == 1


@pytest.mark.asyncio
async def test_first_stop_attempt_tries_another_approach():
    instance, _ = agent(
        [
            INSPECT,
            {"action": "stop", "limitation": "Status meaning is unclear"},
            PROFILE,
            sql_action(),
            FINISH,
        ]
    )
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]


@pytest.mark.asyncio
async def test_diagnostic_evidence_is_used_in_subsequent_generation():
    probe = {
        "action": "investigate_query",
        "sql": "SELECT COUNT(*) AS total FROM dbo.Sales",
        "purpose": "Verify whether the selected source contains records",
    }
    instance, llm = agent(
        [
            INSPECT,
            probe,
            {"action": "generate_sql", "sql": "SELECT Status FROM dbo.Sales", "filters": []},
            FINISH,
        ]
    )
    calls = []

    def inspect_query(sql):
        calls.append(sql)
        return {"sql": sql, "rows": [{"total": 42}], "rows_truncated": False}

    instance.inspection.probe = inspect_query
    result = await instance.answer("List sale statuses", "", [])
    assert result.output["ready_to_execute"]
    assert len(calls) == 1
    assert "42" in llm.prompts[2] and "diagnostic_evidence" in llm.prompts[2]


@pytest.mark.asyncio
async def test_round_limit_can_offer_choices_instead_of_silent_failure():
    instance, _ = agent(
        [INSPECT, PROFILE, {"clarification_questions": CLARIFY["clarification_questions"]}],
        max_rounds=2,
    )
    result = await instance.answer("Show qualifying sales", "", [])
    assert not result.output["ready_to_execute"]
    assert result.output["clarification_questions"]


@pytest.mark.asyncio
async def test_deep_clarification_reply_preserves_original_goal_and_resumes(monkeypatch):
    import agents.orchestrator as module

    instance, llm = agent([INSPECT, PROFILE, CLARIFY, INSPECT, PROFILE, sql_action(), FINISH])

    def factory(metered, *args, **kwargs):
        instance.llm = metered
        return instance

    monkeypatch.setattr(module, "DeepSqlAgent", factory)
    settings = Settings(_env_file=None, llm_provider="mock", qdrant_enabled=False)
    memory = ConversationMemory()
    orchestrator = AgentOrchestrator(
        llm, memory, object(), PdfTool(), DocumentTool(), RagPipeline(settings)
    )
    first = await orchestrator.chat(
        ChatRequest(
            query="Show qualifying sales",
            session_id="clarification-chat",
            deep_sql_automatic_mode=True,
        )
    )
    assert first.status == "needs_clarification"
    assert len(first.clarification_options) == 2
    assert "clarification-chat" in memory.pending
    second = await orchestrator.chat(
        ChatRequest(
            query="Active only, all available dates",
            session_id="clarification-chat",
            deep_sql_automatic_mode=True,
        )
    )
    assert second.status == "query_ready"
    assert "Show qualifying sales" in llm.prompts[-1]
    assert "Active only, all available dates" in llm.prompts[-1]
    assert "clarification-chat" not in memory.pending


def test_diagnostic_probe_is_bounded_and_marks_omitted_values(monkeypatch):
    from contextlib import contextmanager

    class Cursor:
        description = [("note",)]

        def fetchmany(self, size):
            assert size == 6
            return [("x" * 1000,)] * 6

    class Tool:
        @contextmanager
        def query_cursor(self, sql):
            yield Cursor()

    inspection = DeepSqlInspection(Tool())
    monkeypatch.setattr(inspection, "compile", lambda sql: ["note"])
    result = inspection.probe("SELECT note FROM dbo.Sales")
    assert len(result["rows"]) == 5
    assert result["rows_truncated"]
    assert result["omitted_cells"] == 5
    assert result["rows"][0]["note"]["omitted"]


@pytest.mark.parametrize(
    "dtype,stored,declared",
    [("bit", True, 1), ("boolean", False, 0), ("decimal", "1.00", 1), ("integer", 1, "1")],
)
def test_verified_filter_values_use_column_types_not_python_json_types(dtype, stored, declared):
    schema = {
        "columns": [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Sales",
                "COLUMN_NAME": "Status",
                "DATA_TYPE": dtype,
            }
        ]
    }
    profiles = {
        "one": {
            "schema": "dbo",
            "table": "Sales",
            "column": "Status",
            "values": [stored],
            "search": None,
            "truncated": False,
            "omitted_long_values": 0,
        }
    }
    filters = [{"schema": "dbo", "table": "Sales", "column": "Status", "values": [declared]}]
    DeepSqlAgent._verify_filters(filters, profiles, schema)


def test_text_codes_keep_exact_meaning_instead_of_numeric_coercion():
    schema = {
        "columns": [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Sales",
                "COLUMN_NAME": "Status",
                "DATA_TYPE": "varchar",
            }
        ]
    }
    profiles = {
        "one": {
            "schema": "dbo",
            "table": "Sales",
            "column": "Status",
            "values": ["01"],
            "search": None,
            "truncated": False,
            "omitted_long_values": 0,
        }
    }
    with pytest.raises(ValueError, match="not verified"):
        DeepSqlAgent._verify_filters(
            [{"schema": "dbo", "table": "Sales", "column": "Status", "values": [1]}],
            profiles,
            schema,
        )


@pytest.mark.asyncio
async def test_transient_model_failure_retries_without_leaking_private_error_text():
    instance, _ = agent([])
    outputs = iter(
        [INSPECT, PROFILE, RuntimeError("private service credential"), sql_action(), FINISH]
    )

    class Client:
        async def generate(self, prompt, **kwargs):
            value = next(outputs)
            if isinstance(value, Exception):
                raise value
            import json

            return json.dumps(value)

    instance.llm = Client()
    result = await instance.answer("Show active sales", "", [])
    assert result.output["ready_to_execute"]
    assert result.output["rounds"] == 5
    assert "private service credential" not in str(result.output)
