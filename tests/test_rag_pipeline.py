from config.settings import Settings
from rag.pipeline import RagPipeline


def test_rag_ingest_and_retrieve():
    rag = RagPipeline(Settings())
    rag.ingest_text("Refund policy allows returns within 30 days with a receipt.", "policy.md")
    hits = rag.retrieve("refund returns")
    assert hits
    assert "Refund policy" in hits[0][0].text

