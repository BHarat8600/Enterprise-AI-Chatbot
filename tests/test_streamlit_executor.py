from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
import json

from streamlit.testing.v1 import AppTest


@patch("httpx.get")
def test_review_edit_and_execute_keeps_data_out_of_chat(get):
    get.return_value.json.return_value = {}
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py", default_timeout=10
    ).run()
    app.session_state["last_response"] = {
        "answer": "Query ready",
        "status": "query_ready",
        "timeline": [],
        "citations": [],
        "metrics": {"tool_success_rate": 1, "latency_ms": 1},
        "judge": {},
        "tool_results": [
            {
                "tool": "sql",
                "success": True,
                "output": {
                    "sql": "SELECT id FROM sales",
                    "engine": "sqlserver",
                    "column_count": 1,
                    "columns": ["id"],
                    "ready_to_execute": True,
                },
            }
        ],
    }
    app.session_state["query_database"] = {"engine": "sqlserver"}
    app.run()
    assert not app.exception
    editor = next(
        element for element in app.text_area if element.label.startswith("SQL to execute")
    )
    editor.set_value("SELECT id FROM sales ORDER BY id")
    with patch("httpx.post") as post:
        post.return_value.json.return_value = {
            "sql": editor.value,
            "columns": ["id"],
            "column_count": 1,
            "row_count": 50,
            "rows": [{"id": "SENSITIVE_RETURNED_ROW"}] + [{"id": i} for i in range(4)],
            "report_id": "report",
            "llm_calls": 0,
            "total_tokens": 0,
        }
        next(button for button in app.button if button.label == "Execute").click().run()
    assert not app.exception
    assert post.call_args.args[0].endswith("/database/execute")
    assert post.call_args.kwargs["json"]["sql"] == "SELECT id FROM sales ORDER BY id"
    assert app.session_state["messages"] == []
    assert any("LLM tokens: 0" in element.value for element in app.caption)
    assert len(app.session_state["database_execution"]["data"]["rows"]) == 5
    next(
        element for element in app.text_area if element.label.startswith("Optional changes")
    ).set_value("Add region column").run()
    captured = {}

    @contextmanager
    def stream(method, url, **kwargs):
        captured.update(kwargs["json"])

        class Response:
            def raise_for_status(self):
                pass

            def iter_lines(self):
                return iter(
                    [
                        json.dumps(
                            {
                                "type": "result",
                                "data": {
                                    "answer": "Revised SQL ready",
                                    "status": "query_ready",
                                    "timeline": [],
                                    "tool_results": [],
                                    "citations": [],
                                    "metrics": {"tool_success_rate": 1, "latency_ms": 1},
                                    "judge": {},
                                },
                            }
                        )
                    ]
                )

        yield Response()

    with patch("httpx.stream", stream):
        next(button for button in app.button if button.label == "Update query").click().run()
    assert not app.exception
    assert "Add region column" in captured["query"]
    assert "SELECT id FROM sales ORDER BY id" in captured["query"]
    assert "SENSITIVE_RETURNED_ROW" not in json.dumps(captured)
