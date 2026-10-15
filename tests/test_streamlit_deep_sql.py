import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


@patch("httpx.get")
def test_deep_sql_control_is_separate_and_routes_its_own_flag(get):
    get.return_value.json.return_value = {}
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py", default_timeout=10
    ).run()
    assert not app.exception
    automatic = next(t for t in app.toggle if t.label == "Automatic Mode")
    automatic.set_value(True).run()
    deep = next(t for t in app.toggle if t.label == "Deep SQL Automatic Mode")
    deep.set_value(True).run()
    assert next(t for t in app.toggle if t.label == "Deep SQL Automatic Mode").value
    assert not next(t for t in app.toggle if t.label == "Automatic Mode").value
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
                                    "answer": "Deep SQL ready",
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
        app.chat_input[0].set_value("Show active sales").run()
    assert not app.exception
    assert captured["deep_sql_automatic_mode"] is True
    assert captured["automatic_mode"] is False
    assert captured["defer_database_execution"] is True
    next(t for t in app.toggle if t.label == "Automatic Mode").set_value(True).run()
    assert not next(t for t in app.toggle if t.label == "Deep SQL Automatic Mode").value


@patch("httpx.get")
def test_deep_clarification_form_displays_alternatives_and_submits_all_answers(get):
    get.return_value.json.return_value = {}
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py", default_timeout=10
    ).run()
    next(t for t in app.toggle if t.label == "Deep SQL Automatic Mode").set_value(True).run()
    app.session_state["last_response"] = {
        "answer": "Please clarify",
        "status": "needs_clarification",
        "clarification_options": [
            {"question": "Which active definition?", "options": ["Active only", "All statuses"]},
            {"question": "Which dates?", "options": ["All dates", "Current period"]},
        ],
        "timeline": [],
        "tool_results": [],
        "citations": [],
        "metrics": {"tool_success_rate": 1, "latency_ms": 1},
        "judge": {},
    }
    app.run()
    assert not app.exception
    assert len(app.radio) == 2
    app.radio[0].set_value("Active only")
    app.radio[1].set_value("All dates")
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
                                    "answer": "Resumed investigation",
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
        next(b for b in app.button if b.label == "Submit clarification").click().run()
    assert not app.exception
    assert "Active only" in captured["query"] and "All dates" in captured["query"]
    assert captured["deep_sql_automatic_mode"]
