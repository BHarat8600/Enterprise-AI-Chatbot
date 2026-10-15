"""Observable investigation summaries and cancellable UI pacing; no model reasoning traces."""

import asyncio
from datetime import UTC, datetime
from time import perf_counter

from services.llm import usage_context


def investigation_question(step):
    lower = step.lower()
    if "identify tables" in lower:
        return "Which database tables are available for this request?"
    if "columns" in lower:
        return "Which actual columns support the request?"
    if "data types" in lower:
        return "Which column types must the query respect?"
    if "relationships" in lower:
        return "Which verified keys and relationships support the joins?"
    if "distinct" in lower:
        return "Which stored values resolve this categorical condition?"
    if "diagnostic" in lower:
        return "What additional database evidence resolves the uncertainty?"
    if "validate sql" in lower or "goal review" in lower:
        return "Does the SQL match the schema and satisfy the requested goal?"
    if "clarification" in lower:
        return "Which unresolved business choice requires a user answer?"
    return "What is the next useful investigation step toward the goal?"


class DeepSqlProgress:
    def __init__(
        self,
        sink,
        minimum=15,
        large_minimum=30,
        large_tokens=4000,
        now=perf_counter,
        sleep=asyncio.sleep,
    ):
        self.sink, self.minimum, self.large_minimum = sink, minimum, large_minimum
        self.large_tokens, self.now, self.sleep = large_tokens, now, sleep
        self.started = {}

    async def __call__(self, event):
        step, status = event["step"], event["status"]
        current = usage_context.get()
        tokens = current.input_tokens + current.output_tokens if current else 0
        if status == "In Progress" and step not in self.started:
            self.started[step] = (self.now(), tokens)
        start, baseline = self.started.get(step, (self.now(), tokens))
        used = max(0, tokens - baseline)
        used = max(used, event.get("step_tokens", 0))
        target = self.large_minimum if used >= self.large_tokens else self.minimum
        enriched = {
            **event,
            "question": event.get("question") or investigation_question(step),
            "step_tokens": used,
            "duration_target_seconds": target,
        }
        if status in {"Completed", "Failed"} and step in self.started:
            remaining = target - (self.now() - start)
            if remaining > 0:
                await self.sink(
                    {
                        **enriched,
                        "status": "In Progress",
                        "detail": "Step work finished; keeping its evidence summary visible for the requested pacing.",
                        "outcome": event.get("detail", ""),
                        "elapsed_seconds": round(self.now() - start, 2),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                while remaining > 0:
                    await self.sleep(min(1.0, remaining))
                    remaining = target - (self.now() - start)
                    if remaining > 0:
                        await self.sink(
                            {
                                **enriched,
                                "status": "In Progress",
                                "detail": "Evidence ready; step visibility countdown is running.",
                                "outcome": event.get("detail", ""),
                                "elapsed_seconds": round(self.now() - start, 2),
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )
            self.started.pop(step, None)
        enriched["elapsed_seconds"] = round(self.now() - start, 2)
        enriched["timestamp"] = datetime.now(UTC).isoformat()
        if status in {"Completed", "Failed"}:
            enriched["outcome"] = event.get("detail", "")
        await self.sink(enriched)
