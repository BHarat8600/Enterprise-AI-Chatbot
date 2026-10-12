import asyncio
import json

import pytest

from memory.store import ConversationMemory
from models.schemas import ChatMessage, ExecutionPlan
from agents.response_agent import ResponseGenerationAgent
from services.llm import MeteredClient, TokenUsage, usage_context


def test_relevant_memory_keeps_old_facts_and_isolates_chats():
    memory = ConversationMemory(max_messages=2)
    memory.add("one", ChatMessage(role="user", content="Revenue excludes tax in the BRD."))
    memory.add("one", ChatMessage(role="assistant", content="Understood."))
    for i in range(20):
        memory.add("one", ChatMessage(role="user", content=f"Unrelated topic {i}"))
        memory.add("one", ChatMessage(role="assistant", content="Okay."))
    assert "excludes tax" in memory.relevant("one", "Revenue BRD")
    assert "excludes tax" not in memory.relevant("two", "Revenue BRD")
    assert len(memory.relevant("one", "Revenue BRD", budget=100)) <= 100


class FakeClient:
    async def generate(self, prompt, **kwargs):
        await asyncio.sleep(0)
        return json.dumps({"answer": "Unverified claim", "confidence": 0.2, "clarification_questions": []})


@pytest.mark.asyncio
async def test_low_confidence_cannot_publish_speculation():
    agent = ResponseGenerationAgent(FakeClient())
    result = await agent.assess("Revenue?", ExecutionPlan(intent="answer"), [], "")
    assert not result["clarification_questions"]
    assert result["status"] == "insufficient_evidence"
    assert "Unverified claim" not in result["answer"]


@pytest.mark.asyncio
async def test_usage_is_request_local_and_restored():
    async def run(prompt):
        usage = TokenUsage()
        token = usage_context.set(usage)
        try:
            await MeteredClient(FakeClient()).generate(prompt)
            return usage
        finally:
            usage_context.reset(token)
    short, long = await asyncio.gather(run("x"), run("x" * 100))
    assert short.llm_calls == long.llm_calls == 1
    assert short.input_tokens < long.input_tokens
    assert short.tokens_estimated
    assert usage_context.get() is None
