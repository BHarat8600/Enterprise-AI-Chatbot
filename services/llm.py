from abc import ABC, abstractmethod
from typing import Any
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    tokens_estimated: bool = False


usage_context: ContextVar[TokenUsage | None] = ContextVar("token_usage", default=None)


def record_usage(prompt: str, answer: str, usage: dict | None = None) -> None:
    current = usage_context.get()
    if current is None:
        return
    current.llm_calls += 1
    if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
        current.input_tokens += usage["prompt_tokens"]
        current.output_tokens += usage["completion_tokens"]
    else:
        current.tokens_estimated = True
        current.input_tokens += (len(prompt) + 3) // 4
        current.output_tokens += (len(answer) + 3) // 4


class MeteredClient:
    """Fallback metering for mock/custom clients that do not report provider usage."""
    def __init__(self, client):
        self.client = client

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        current = usage_context.get()
        before = current.llm_calls if current else 0
        answer = await self.client.generate(prompt, **kwargs)
        if current and current.llm_calls == before:
            record_usage(prompt, answer)
        return answer


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        if "ANSWER_ASSESSMENT_JSON" in prompt:
            return '{"answer":"Mock mode cannot verify an answer. Please provide evidence or configure a live LLM provider.","confidence":0,"clarification_questions":["Can you provide the required evidence or configure a live LLM provider?"]}'
        if "Return a compact JSON execution plan" in prompt:
            query_section = prompt.split("Query:", 1)[-1].split("Files:", 1)[0]
            lower = query_section.lower()
            tools: list[str] = []
            if "sql" in lower or "database" in lower or "table" in lower:
                tools.append("sql")
            if "pdf" in lower:
                tools.append("pdf")
            if any(token in lower for token in ["document", "docx", "csv", "excel", "markdown", "txt"]):
                tools.append("document")
            if any(token in lower for token in ["knowledge", "policy", "retrieve", "rag", "source"]):
                tools.append("rag")
            if not tools:
                tools.append("direct")
            return (
                '{"intent":"answer_user_query","can_answer_directly":'
                + str(tools == ["direct"]).lower()
                + ',"tools":'
                + str(tools).replace("'", '"')
                + ',"risks":[]}'
            )
        return "I analyzed the available context and produced a grounded response from the executed tools."


class OpenAICompatibleClient(LLMClient):
    def __init__(self, base_url: str | None, api_key: str | None, model: str):
        self.base_url = base_url or "https://api.openai.com/v1"
        self.api_key = api_key
        self.model = model

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.2),
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            record_usage(prompt, answer, data.get("usage"))
            return answer


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(None, settings.openai_api_key, settings.llm_model)
    if settings.llm_provider == "groq":
        return OpenAICompatibleClient(settings.groq_base_url, settings.groq_api_key, settings.llm_model)
    if settings.llm_provider == "vllm":
        return OpenAICompatibleClient(settings.vllm_base_url, None, settings.llm_model)
    return MockLLMClient()
