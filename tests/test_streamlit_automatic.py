import json
from contextlib import contextmanager
from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest


@patch("httpx.get")
def test_automatic_toggle_and_streamed_result_render_without_exception(get):
    get.return_value.json.return_value = {}
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py", default_timeout=10).run()
    assert not app.exception
    assert app.toggle[0].label == "Automatic Mode"
    app.toggle[0].set_value(True).run()
    assert not app.exception
    events = [
        {"type": "progress", "step": "Planning", "status": "Pending"},
        {"type": "progress", "step": "Planning", "status": "In Progress"},
        {"type": "progress", "step": "Planning", "status": "Completed", "tools": [], "tool_mode": "No tools"},
        {"type": "result", "data": {"answer": "Hello from Automatic Mode", "status": "answered", "timeline": [],
            "tool_results": [], "citations": [], "metrics": {"tool_success_rate": 1, "latency_ms": 1}, "judge": {}}},
    ]
    captured = {}

    @contextmanager
    def stream(method, url, **kwargs):
        captured.update(kwargs["json"])

        class Response:
            def raise_for_status(self):
                pass

            def iter_lines(self):
                return iter(json.dumps(event) for event in events)

        yield Response()

    with patch("httpx.stream", stream):
        app.chat_input[0].set_value("Hello").run()
    assert not app.exception
    assert captured["automatic_mode"] is True
    assert app.session_state["messages"][-1]["content"] == "Hello from Automatic Mode"
