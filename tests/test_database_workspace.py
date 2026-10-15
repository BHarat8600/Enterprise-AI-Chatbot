import csv
from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest

from agents.database_agent import DatabaseAgent, validate_read_only
from agents.orchestrator import AgentOrchestrator
from config.settings import Settings
from memory.store import ConversationMemory
from models.schemas import ChatRequest, DatabaseConfig
from rag.pipeline import RagPipeline
from services.database_connections import connection_settings, public_database_defaults
from services.database_reports import DatabaseReports
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.postgresql_tool import PostgreSQLTool
from tools.sql_tool import SqlServerTool
from test_automatic_mode import Database, SequenceLLM


def test_defaults_and_overrides_do_not_leak_or_mutate_passwords():
    defaults = Settings(
        _env_file=None,
        sqlserver_host="original",
        sqlserver_database="demo",
        sqlserver_user="alice",
        sqlserver_password="private-default",
        postgresql_password="private-pg",
    )
    same = connection_settings(defaults, DatabaseConfig())
    assert same.sqlserver_password == "private-default"
    changed = connection_settings(defaults, DatabaseConfig(host="different"))
    assert changed.sqlserver_password is None
    assert defaults.sqlserver_host == "original"
    assert defaults.sqlserver_password == "private-default"
    explicit = connection_settings(
        defaults, DatabaseConfig(host="different", password="new-private")
    )
    assert explicit.sqlserver_password == "new-private"
    assert "private-default" not in str(public_database_defaults(defaults))
    assert "private-pg" not in str(public_database_defaults(defaults))
    assert "new-private" not in repr(DatabaseConfig(password="new-private"))
    same_explicit = connection_settings(
        defaults, DatabaseConfig(host="original", database="demo", username="alice", dsn="")
    )
    assert same_explicit.sqlserver_password == "private-default"


class ReportTool:
    dialect = "PostgreSQL"

    def __init__(self, count=2005):
        self.count, self.executions = count, 0

    def validate_sql(self, sql):
        PostgreSQLTool(None).validate_sql(sql)

    @contextmanager
    def query_cursor(self, sql):
        self.executions += 1
        count = self.count

        class Cursor:
            description = [("id",), ("description",)]
            offset = 0

            def fetchmany(self, size):
                start, self.offset = self.offset, min(count, self.offset + size)
                return [(i, 'comma,quote"\nline') for i in range(start, self.offset)]

        yield Cursor()


@pytest.mark.parametrize("count", [0, 3, 2005])
def test_executor_previews_five_and_exports_every_row_from_same_execution(tmp_path, count):
    reports = DatabaseReports(tmp_path)
    tool = ReportTool(count)
    result = reports.execute(tool, "SELECT id, description FROM sales", "chat-one")
    assert result["row_count"] == count
    assert result["column_count"] == 2
    assert len(result["rows"]) == min(5, count)
    assert result["llm_calls"] == result["total_tokens"] == 0
    assert tool.executions == 1
    assert reports.get(result["report_id"], "chat-two") is None
    with reports.get(result["report_id"], "chat-one").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        rows = list(csv.reader(file))
    assert len(rows) == count + 1
    assert rows[0] == ["id", "description"]
    if count:
        assert rows[-1][0] == str(count - 1)
        assert rows[-1][1] == 'comma,quote"\nline'


def test_report_expiration_removes_download(tmp_path):
    reports = DatabaseReports(tmp_path, ttl=-1)
    result = reports.execute(ReportTool(1), "SELECT id FROM sales", "chat")
    assert reports.get(result["report_id"], "chat") is None
    assert not list(tmp_path.glob("*.csv"))


def test_executor_blocks_writes_before_opening_connection(tmp_path):
    tool = ReportTool()
    with pytest.raises(ValueError):
        DatabaseReports(tmp_path).execute(
            tool, "WITH changed AS (DELETE FROM sales RETURNING *) SELECT * FROM changed", "chat"
        )
    assert tool.executions == 0


def test_postgresql_allows_casts_but_blocks_session_configuration():
    tool = PostgreSQLTool(None)
    validate_read_only("SELECT amount::numeric FROM public.sales", tool)
    with pytest.raises(ValueError):
        validate_read_only("SELECT set_config('transaction_read_only','off',false)", tool)


@pytest.mark.asyncio
async def test_generate_only_does_not_execute_or_call_response_llm():
    settings = Settings(_env_file=None, llm_provider="mock", qdrant_enabled=False)
    database = Database()
    llm = SequenceLLM(
        [
            {"tools": ["sql"]},
            {"tables": ["dbo.Sales"]},
            {"sql": "SELECT Revenue FROM dbo.Sales", "assumptions": []},
        ]
    )
    memory = ConversationMemory()
    orchestrator = AgentOrchestrator(
        llm, memory, database, PdfTool(), DocumentTool(), RagPipeline(settings)
    )
    result = await orchestrator.chat(
        ChatRequest(query="Show revenue", automatic_mode=True, defer_database_execution=True)
    )
    assert result.status == "query_ready"
    assert database.executions == 0
    assert result.metrics.llm_calls == 3
    assert result.tool_results[0].output["ready_to_execute"]
    assert "row_count" not in result.tool_results[0].output
    assert not any("ANSWER_ASSESSMENT_JSON" in p for p in llm.prompts)


class PostgresCatalog:
    dialect = "PostgreSQL"
    configured = True

    def __init__(self):
        self.steps = []

    def tables(self):
        self.steps.append("tables")
        return [{"TABLE_SCHEMA": "public", "TABLE_NAME": "sales"}]

    def columns(self, tables):
        self.steps.append("columns")
        assert tables[0]["TABLE_NAME"] == "sales"
        return [
            {
                "TABLE_SCHEMA": "public",
                "TABLE_NAME": "sales",
                "COLUMN_NAME": "amount",
                "DATA_TYPE": "numeric",
            }
        ]

    def relationships(self):
        self.steps.append("relationships")
        return []

    def keys(self):
        self.steps.append("keys")
        return []

    def validate_sql(self, sql):
        PostgreSQLTool(None).validate_sql(sql)

    def compile(self, sql):
        self.steps.append("compile")
        assert "::numeric" in sql
        return ["amount"]


@pytest.mark.asyncio
async def test_postgresql_investigates_actual_schema_in_order_and_generates_dialect():
    tool = PostgresCatalog()
    llm = SequenceLLM(
        [{"tables": ["public.sales"]}, {"sql": "SELECT amount::numeric FROM public.sales LIMIT 20"}]
    )
    result = await DatabaseAgent(llm, tool).answer("Show sales amounts", "", [], generate_only=True)
    assert result.success
    assert result.tool.value == "postgresql"
    assert result.output["engine"] == "postgresql"
    assert tool.steps == ["tables", "columns", "relationships", "keys", "compile"]
    assert "numeric" in llm.prompts[-1] and "PostgreSQL SELECT" in llm.prompts[-1]


def test_odbc_password_and_server_values_are_escaped():
    settings = Settings(
        _env_file=None,
        sqlserver_host="server;UID=other",
        sqlserver_database="demo",
        sqlserver_user="alice",
        sqlserver_password="a}b;Trusted_Connection=yes",
        sqlserver_trusted_connection=False,
    )
    connection = SqlServerTool(settings).connection_string()
    assert "SERVER={server;UID=other}" in connection
    assert "PWD={a}}b;Trusted_Connection=yes}" in connection


def test_postgresql_report_does_not_prefetch_and_discard_first_row(tmp_path, monkeypatch):
    cursor = MagicMock()
    cursor.description = [("id",)]
    cursor.fetchmany.side_effect = [[(0,), (1,)], []]
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    tool = PostgreSQLTool(None)
    monkeypatch.setattr(tool, "connect", lambda: connection)
    result = DatabaseReports(tmp_path).execute(tool, "SELECT id FROM sales", "one")
    assert result["row_count"] == 2
    assert result["rows"][0] == {"id": 0}
    assert all(call.args == (1000,) for call in cursor.fetchmany.call_args_list)
