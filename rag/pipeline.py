from pathlib import Path
import hashlib
from uuid import uuid5, NAMESPACE_URL
from time import perf_counter

import numpy as np
from rank_bm25 import BM25Okapi

from config.settings import Settings
from models.schemas import SourceCitation, ToolName, ToolResult
from rag.chunking import Chunk, Chunker


class RagPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.chunker = Chunker()
        self.chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self._qdrant = None
        self._qdrant_ready = False

    def ingest_path(self, path: Path) -> int:
        text = self._extract_text(path)
        new_chunks = self.chunker.chunk(text, str(path))
        self.chunks.extend(new_chunks)
        self._refresh_sparse_index()
        self._upsert_qdrant(new_chunks)
        return len(new_chunks)

    def ingest_text(self, text: str, source: str) -> int:
        new_chunks = self.chunker.chunk(text, source)
        self.chunks.extend(new_chunks)
        self._refresh_sparse_index()
        self._upsert_qdrant(new_chunks)
        return len(new_chunks)

    async def answer(self, query: str) -> ToolResult:
        started = perf_counter()
        try:
            hits = self.retrieve(query)
            citations = [
                SourceCitation(source_id=chunk.id, title=chunk.metadata.get("source", chunk.id), score=score)
                for chunk, score in hits
            ]
            output = {"contexts": [{"id": c.id, "score": s, "text": c.text[:1200]} for c, s in hits]}
            return ToolResult(
                tool=ToolName.rag,
                success=True,
                output=output,
                latency_ms=(perf_counter() - started) * 1000,
                citations=citations,
            )
        except Exception as exc:
            return ToolResult(
                tool=ToolName.rag,
                success=False,
                output=None,
                latency_ms=(perf_counter() - started) * 1000,
                error=str(exc),
            )

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        if self._bm25 is None:
            self._refresh_sparse_index()
        assert self._bm25 is not None
        scores = self._bm25.get_scores(query.lower().split())
        ranked = sorted(zip(self.chunks, scores, strict=False), key=lambda item: item[1], reverse=True)
        sparse_hits = [(chunk, float(score)) for chunk, score in ranked[:top_k]]
        dense_hits = self._search_qdrant(query, top_k)
        merged: dict[str, tuple[Chunk, float]] = {chunk.id: (chunk, score) for chunk, score in sparse_hits}
        for chunk, score in dense_hits:
            existing = merged.get(chunk.id)
            merged[chunk.id] = (chunk, max(score, existing[1]) if existing else score)
        return sorted(merged.values(), key=lambda item: item[1], reverse=True)[:top_k]

    def _refresh_sparse_index(self) -> None:
        tokenized = [chunk.text.lower().split() for chunk in self.chunks]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document

            doc = Document(str(path))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        if suffix in {".csv", ".xls", ".xlsx"}:
            import pandas as pd

            if suffix == ".csv":
                return pd.read_csv(path).to_markdown(index=False)
            return pd.read_excel(path).to_markdown(index=False)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _embedding(self, text: str) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8", errors="ignore")
        counter = 0
        while len(values) < self.settings.embedding_dimension:
            digest = hashlib.sha256(seed + str(counter).encode()).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1
        vector = np.array(values[: self.settings.embedding_dimension], dtype=np.float32)
        norm = np.linalg.norm(vector)
        return (vector / norm if norm else vector).tolist()

    def _get_qdrant(self):
        if not self.settings.qdrant_enabled:
            return None
        if self._qdrant is not None:
            return self._qdrant
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams

            client = QdrantClient(url=self.settings.qdrant_url)
            collections = [item.name for item in client.get_collections().collections]
            if self.settings.qdrant_collection not in collections:
                client.create_collection(
                    collection_name=self.settings.qdrant_collection,
                    vectors_config=VectorParams(size=self.settings.embedding_dimension, distance=Distance.COSINE),
                )
            self._qdrant = client
            self._qdrant_ready = True
            return client
        except Exception:
            self._qdrant_ready = False
            return None

    def _upsert_qdrant(self, chunks: list[Chunk]) -> None:
        client = self._get_qdrant()
        if client is None or not chunks:
            return
        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.id)),
                vector=self._embedding(chunk.text),
                payload={"chunk_id": chunk.id, "text": chunk.text, **chunk.metadata},
            )
            for chunk in chunks
        ]
        client.upsert(collection_name=self.settings.qdrant_collection, points=points)

    def _search_qdrant(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        client = self._get_qdrant()
        if client is None:
            return []
        hits = client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=self._embedding(query),
            limit=top_k,
            with_payload=True,
        )
        results: list[tuple[Chunk, float]] = []
        for hit in hits:
            payload = hit.payload or {}
            chunk = Chunk(
                id=str(payload.get("chunk_id", hit.id)),
                text=str(payload.get("text", "")),
                metadata={key: str(value) for key, value in payload.items() if key not in {"chunk_id", "text"}},
            )
            results.append((chunk, float(hit.score)))
        return results
