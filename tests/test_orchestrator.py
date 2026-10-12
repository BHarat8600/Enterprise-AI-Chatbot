import pytest

from agents.orchestrator import AgentOrchestrator
from config.settings import Settings
from memory.store import ConversationMemory
from models.schemas import ChatRequest
from rag.pipeline import RagPipeline
from services.llm import MockLLMClient
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.sql_tool import SqlServerTool


@pytest.mark.asyncio
async def test_orchestrator_returns_chat_response():
    settings = Settings(llm_provider="mock", qdrant_enabled=False)
    orchestrator = AgentOrchestrator(
        llm=MockLLMClient(),
        memory=ConversationMemory(),
        sql_tool=SqlServerTool(settings),
        pdf_tool=PdfTool(),
        document_tool=DocumentTool(),
        rag=RagPipeline(settings),
    )
    response = await orchestrator.chat(ChatRequest(query="What can you do?"))
    assert response.session_id
    assert response.answer
    assert response.metrics.tool_success_rate >= 0
    assert response.metrics.llm_calls == 2
    assert response.metrics.total_tokens > 0
    assert response.status == "needs_clarification"
    assert response.session_id in orchestrator.memory.pending
    other = ChatRequest(query="What can you do?")
    assert other.session_id != response.session_id
    assert orchestrator.memory.relevant(other.session_id, other.query) == ""
