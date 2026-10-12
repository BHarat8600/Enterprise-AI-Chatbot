from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


class Chunker:
    def chunk(self, text: str, source: str, chunk_size: int = 900, overlap: int = 120) -> list[Chunk]:
        suffix = Path(source).suffix.lower()
        if suffix == ".sql":
            return self.statement_aware(text, source)
        if suffix == ".md":
            return self.markdown_aware(text, source)
        return self.recursive(text, source, chunk_size, overlap)

    def recursive(self, text: str, source: str, chunk_size: int, overlap: int) -> list[Chunk]:
        chunks: list[Chunk] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunks.append(Chunk(f"{source}:{len(chunks)}", text[start:end], {"source": source}))
            start = max(end - overlap, end) if end == len(text) else end - overlap
        return chunks

    def markdown_aware(self, text: str, source: str) -> list[Chunk]:
        sections = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("#") and current:
                sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current))
        return [Chunk(f"{source}:section:{i}", section, {"source": source, "type": "markdown"}) for i, section in enumerate(sections)]

    def statement_aware(self, text: str, source: str) -> list[Chunk]:
        statements = [part.strip() for part in text.split(";") if part.strip()]
        return [Chunk(f"{source}:sql:{i}", statement, {"source": source, "type": "sql"}) for i, statement in enumerate(statements)]

