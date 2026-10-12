from functools import lru_cache

from agents.orchestrator import AgentOrchestrator
from config.settings import get_settings
from memory.store import ConversationMemory
from rag.pipeline import RagPipeline
from services.llm import build_llm_client
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.sql_tool import SqlServerTool


@lru_cache(maxsize=1)
def get_orchestrator() -> AgentOrchestrator:
    settings = get_settings()
    llm = build_llm_client(settings)
    memory = ConversationMemory()
    rag = RagPipeline(settings)
    return AgentOrchestrator(
        llm=llm,
        memory=memory,
        sql_tool=SqlServerTool(settings),
        pdf_tool=PdfTool(),
        document_tool=DocumentTool(),
        rag=rag,
    )

