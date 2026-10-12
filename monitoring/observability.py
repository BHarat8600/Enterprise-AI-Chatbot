from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import Counter, Histogram

TOOL_CALLS = Counter("chatbot_tool_calls_total", "Tool calls", ["tool", "success"])
TOOL_LATENCY = Histogram("chatbot_tool_latency_seconds", "Tool latency", ["tool"])
CHAT_LATENCY = Histogram("chatbot_chat_latency_seconds", "End-to-end chat latency")


def configure_tracing() -> None:
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(TracerProvider())


@contextmanager
def timed_tool(tool: str) -> Iterator[dict[str, float]]:
    started = perf_counter()
    info: dict[str, float] = {}
    try:
        yield info
        TOOL_CALLS.labels(tool=tool, success="true").inc()
    except Exception:
        TOOL_CALLS.labels(tool=tool, success="false").inc()
        raise
    finally:
        elapsed = perf_counter() - started
        info["latency_ms"] = elapsed * 1000
        TOOL_LATENCY.labels(tool=tool).observe(elapsed)

