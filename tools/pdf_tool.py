from pathlib import Path
from time import perf_counter

from models.schemas import SourceCitation, ToolName, ToolResult


class PdfTool:
    async def answer(self, query: str, files: list[str]) -> ToolResult:
        started = perf_counter()
        pdfs = [Path(path) for path in files if path.lower().endswith(".pdf")]
        try:
            pages: list[str] = []
            citations: list[SourceCitation] = []
            for pdf in pdfs:
                text = self.extract_text(pdf)
                pages.append(text)
                citations.append(SourceCitation(source_id=str(pdf), title=pdf.name, location=str(pdf)))
            output = {"summary": self.summarize("\n".join(pages), query), "documents": [p.name for p in pdfs]}
            return ToolResult(
                tool=ToolName.pdf,
                success=True,
                output=output,
                latency_ms=(perf_counter() - started) * 1000,
                citations=citations,
            )
        except Exception as exc:
            return ToolResult(
                tool=ToolName.pdf,
                success=False,
                output=None,
                latency_ms=(perf_counter() - started) * 1000,
                error=str(exc),
            )

    def extract_text(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
        return "[OCR required: install/configure Tesseract and render scanned pages for OCR]"

    def summarize(self, text: str, query: str) -> str:
        if not text.strip():
            return "No PDF text was extracted."
        if any(term in query.lower() for term in ["brd", "requirement", "clarification"]):
            return text
        return text[:1500]
