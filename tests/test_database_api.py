import csv
import io

from fastapi.testclient import TestClient

from config.settings import Settings
from services.database_reports import DatabaseReports
from test_database_workspace import ReportTool


def test_execute_api_and_report_download_do_not_invoke_chat(tmp_path, monkeypatch):
    import api.main as api

    tool = ReportTool(12)
    monkeypatch.setattr(api, "reports", DatabaseReports(tmp_path))
    monkeypatch.setattr(api, "database_tool", lambda *args: tool)

    def forbidden(*args, **kwargs):
        raise AssertionError("Direct execution must not initialize the chat/LLM")

    monkeypatch.setattr(api, "get_orchestrator", forbidden)
    client = TestClient(api.app)
    response = client.post(
        "/database/execute",
        json={
            "session_id": "one",
            "sql": "SELECT id FROM sales",
            "database": {"engine": "postgresql"},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert len(result["rows"]) == 5 and result["row_count"] == 12
    assert tool.executions == 1
    assert result["llm_calls"] == 0
    url = "/database/reports/" + result["report_id"]
    assert client.get(url, params={"session_id": "two"}).status_code == 404
    report = client.get(url, params={"session_id": "one"})
    assert report.status_code == 200
    rows = list(csv.reader(io.StringIO(report.content.decode("utf-8-sig"))))
    assert len(rows) == 13
    assert "attachment" in report.headers["content-disposition"]


def test_defaults_and_connection_errors_never_return_passwords(monkeypatch):
    import api.main as api

    monkeypatch.setattr(
        api,
        "settings",
        Settings(_env_file=None, sqlserver_password="env-secret", postgresql_password="pg-secret"),
    )

    def bad(*args):
        raise RuntimeError("env-secret pg-secret user-password")

    monkeypatch.setattr(api, "database_tool", bad)
    client = TestClient(api.app)
    defaults = client.get("/database/defaults")
    assert defaults.status_code == 200
    assert all(secret not in defaults.text for secret in ["env-secret", "pg-secret"])
    response = client.post("/database/test", json={"password": "user-password"})
    assert response.json()["connected"] is False
    assert "user-password" not in response.text
    response = client.post(
        "/database/execute",
        json={"session_id": "one", "sql": "SELECT 1", "database": {"password": "user-password"}},
    )
    assert response.status_code == 400
    assert all(
        secret not in response.text for secret in ["env-secret", "pg-secret", "user-password"]
    )
