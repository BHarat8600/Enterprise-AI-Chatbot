from contextvars import ContextVar
from typing import Awaitable, Callable


progress_sink: ContextVar[Callable[[dict], Awaitable[None]] | None] = ContextVar("progress_sink", default=None)


async def progress(step: str, status: str, detail: str = "", **extra) -> None:
    sink = progress_sink.get()
    if sink:
        await sink({"type": "progress", "step": step, "status": status, "detail": detail, **extra})
