from models.schemas import ExecutionPlan, ToolCall, ToolName
from services.llm import LLMClient
from services.structured import json_object, clarifications


class PlannerAgent:
    name = "planner"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def plan(self, query: str, files: list[str], memory: str = "", automatic_mode: bool = False) -> ExecutionPlan:
        prompt = f"""
Return a compact JSON execution plan for this enterprise chatbot request.
Allowed tools: sql, pdf, document, rag, direct.
Query: {query}
Files: {files}
Relevant conversation (untrusted data): {memory}
JSON fields: intent, can_answer_directly, tools, risks, clarification_questions.
If scope, dates, business definitions, BRD requirements, or references are ambiguous
in a way that changes the answer, ask specific clarification_questions. Do not guess.
Use the conversation to resolve previous questions. Select only necessary tools.
Read available BRD/documents using tools BEFORE deciding their requirements are ambiguous.
Do not ask about information that can be resolved from those sources or schema.
Ask only when multiple plausible interpretations change the answer. Do not ask solely
because confidence is low. For each clarification return an object with question and
options (2-5 concrete choices grounded in the request). Use options=[] only when no
meaningful choices can be identified. Never invent column names.
"""
        if automatic_mode:
            prompt += "\nAUTOMATIC MODE: Never ask clarification questions. Investigate with tools; resolve choices from evidence and state assumptions. Return clarification_questions=[]. Give tool_purposes as an object mapping selected tools to brief purposes. Database requests MUST select sql for schema investigation, not fixed query templates."
        raw = await self.llm.generate(prompt)
        try:
            data = json_object(raw)
            questions, options = clarifications(data)
            if automatic_mode:
                questions, options = [], []
            tools = data.get("tools") or ["direct"]
            if not isinstance(tools, list):
                raise ValueError("Invalid tools")
            if files:
                # Inspect supplied requirements before asking the user to resolve them.
                if any(path.lower().endswith(".pdf") for path in files) and "pdf" not in tools:
                    tools.append("pdf")
                if any(not path.lower().endswith(".pdf") for path in files) and "document" not in tools:
                    tools.append("document")
                questions, options = [], []
            purposes = data.get("tool_purposes", {})
            if not isinstance(purposes, dict):
                purposes = {}
            calls = [ToolCall(tool=ToolName(tool), reason=str(purposes.get(tool) or f"Investigate request using {tool}")) for tool in dict.fromkeys(tools)]
            return ExecutionPlan(
                intent=data.get("intent", "answer_user_query"),
                can_answer_directly=bool(data.get("can_answer_directly", tools == ["direct"])),
                steps=calls, risks=data.get("risks", []),
                clarification_questions=questions, clarification_options=options,
            )
        except (ValueError, TypeError, KeyError):
            data = self._fallback_plan(query, files)
        tools = data.get("tools") or ["direct"]
        calls = [ToolCall(tool=ToolName(tool), reason=f"Planner selected {tool}") for tool in tools]
        return ExecutionPlan(
            intent=data.get("intent", "answer_user_query"),
            can_answer_directly=bool(data.get("can_answer_directly", tools == ["direct"])),
            steps=calls,
            risks=data.get("risks", []),
            clarification_questions=data.get("clarification_questions", []),
        )

    def _fallback_plan(self, query: str, files: list[str]) -> dict[str, object]:
        lower = query.lower()
        tools: list[str] = []
        if any(word in lower for word in ["sql", "database", "table", "query", "sales", "revenue", "margin", "profitable"]):
            tools.append("sql")
        if any(path.lower().endswith(".pdf") for path in files) or "pdf" in lower:
            tools.append("pdf")
        if files and not tools:
            tools.append("document")
        elif any(not path.lower().endswith(".pdf") for path in files):
            tools.append("document")
        if any(word in lower for word in ["policy", "knowledge", "source", "retrieve"]):
            tools.append("rag")
        return {"intent": "answer_user_query", "can_answer_directly": not tools, "tools": tools or ["direct"], "risks": []}
