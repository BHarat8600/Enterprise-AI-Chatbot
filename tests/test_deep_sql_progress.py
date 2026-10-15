import pytest

from services.deep_sql_progress import DeepSqlProgress
from services.llm import TokenUsage, usage_context


@pytest.mark.asyncio
@pytest.mark.parametrize("tokens,expected", [(100, 15), (4000, 30)])
async def test_step_pacing_uses_actual_token_delta_without_real_sleep(tokens, expected):
    events, waits = [], []
    now = [0.0]

    async def emit(event):
        events.append(event)

    async def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    usage = TokenUsage()
    token = usage_context.set(usage)
    try:
        paced = DeepSqlProgress(emit, now=lambda: now[0], sleep=sleep)
        await paced(
            {"step": "Deep SQL round 1", "status": "In Progress", "detail": "Checking schema"}
        )
        now[0] = 2
        usage.input_tokens = tokens
        await paced(
            {"step": "Deep SQL round 1", "status": "Completed", "detail": "Verified evidence"}
        )
    finally:
        usage_context.reset(token)
    assert sum(waits) == expected - 2
    assert events[-1]["elapsed_seconds"] == expected
    assert events[-1]["step_tokens"] == tokens
    assert events[-1]["outcome"] == "Verified evidence"
    assert events[-1]["question"]
    assert events[-2]["status"] == "In Progress"


@pytest.mark.asyncio
async def test_slow_step_gets_no_extra_wait():
    events, waits = [], []
    now = [0.0]

    async def emit(event):
        events.append(event)

    async def sleep(seconds):
        waits.append(seconds)

    paced = DeepSqlProgress(emit, now=lambda: now[0], sleep=sleep)
    await paced({"step": "Deep SQL: identify tables", "status": "In Progress"})
    now[0] = 40
    await paced(
        {"step": "Deep SQL: identify tables", "status": "Completed", "detail": "Tables found"}
    )
    assert not waits
    assert events[-1]["elapsed_seconds"] == 40
