import asyncio
import json

from services.progress import progress_sink


async def chat_events(orchestrator, payload):
    """NDJSON progress delivered while work runs, followed by one final response."""
    queue = asyncio.Queue()

    async def run():
        token = progress_sink.set(queue.put)
        try:
            response = await orchestrator.chat(payload)
            await queue.put({"type": "result", "data": response.model_dump(mode="json")})
        except Exception:
            await queue.put({"type": "error", "message": "The request could not be completed. Please retry."})
        finally:
            progress_sink.reset(token)

    task = asyncio.create_task(run())
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield json.dumps({"type": "heartbeat"}) + "\n"
                continue
            yield json.dumps(event, ensure_ascii=False) + "\n"
            if event["type"] in {"result", "error"}:
                break
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
