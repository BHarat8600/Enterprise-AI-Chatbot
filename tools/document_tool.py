from pathlib import Path
from time import perf_counter

import pandas as pd

from models.schemas import SourceCitation, ToolName, ToolResult


class DocumentTool:
    async def answer(self, query: str, files: list[str]) -> ToolResult:
        started = perf_counter()
        try:
            documents = [{"path": path, "text": self.read(Path(path))} for path in files if not path.lower().endswith(".pdf")]
            citations = [
                SourceCitation(source_id=item["path"], title=Path(item["path"]).name, location=item["path"])
                for item in documents
            ]
            output = {
                "matches": self.search(query, documents),
                "summaries": [{**item, "text": item["text"][:1200]} for item in documents],
            }
            if any(term in query.lower() for term in ["brd", "requirement", "clarification"]):
                output["requirements_documents"] = documents
            return ToolResult(
                tool=ToolName.document,
                success=True,
                output=output,
                latency_ms=(perf_counter() - started) * 1000,
                citations=citations,
            )
        except Exception as exc:
            return ToolResult(
                tool=ToolName.document,
                success=False,
                output=None,
                latency_ms=(perf_counter() - started) * 1000,
                error=str(exc),
            )

    def read(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            from docx import Document

            doc = Document(str(path))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        if suffix == ".csv":
            return pd.read_csv(path).to_markdown(index=False)
        if suffix in {".xls", ".xlsx"}:
            return pd.read_excel(path).to_markdown(index=False)
        return path.read_text(encoding="utf-8", errors="ignore")

    def search(self, query: str, documents: list[dict[str, str]]) -> list[dict[str, str]]:
        terms = {term.lower() for term in query.split() if len(term) > 2}
        matches: list[dict[str, str]] = []
        for document in documents:
            lines = document["text"].splitlines()
            for index, line in enumerate(lines, start=1):
                if any(term in line.lower() for term in terms):
                    matches.append({"path": document["path"], "line": str(index), "text": line[:500]})
        return matches[:20]
