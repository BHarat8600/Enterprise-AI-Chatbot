from time import perf_counter
import logging
import asyncio
import json

from agents.guardrail_agent import GuardrailAgent
from agents.judge_agent import LLMJudgeAgent
from agents.planner_agent import PlannerAgent
from agents.response_agent import ResponseGenerationAgent
from agents.validation_agent import ValidationAgent
from evaluation.metrics import MetricsEvaluator
from memory.store import ConversationMemory
from models.schemas import ChatMessage, ChatRequest, ChatResponse, ToolName, ToolResult
from rag.pipeline import RagPipeline
from services.llm import LLMClient, MeteredClient, TokenUsage, usage_context
from services.structured import question_answer
from models.schemas import ExecutionPlan, GuardrailResult, JudgeResult
from tools.document_tool import DocumentTool
from tools.pdf_tool import PdfTool
from tools.sql_tool import SqlServerTool
from agents.database_agent import DatabaseAgent
from services.progress import progress, progress_sink


class AgentOrchestrator:
    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        sql_tool: SqlServerTool,
        pdf_tool: PdfTool,
        document_tool: DocumentTool,
        rag: RagPipeline,
    ):
        self.memory = memory
        llm = MeteredClient(llm)
        self.guardrails = GuardrailAgent()
        self.planner = PlannerAgent(llm)
        self.database_agent = DatabaseAgent(llm, sql_tool)
        self.response_agent = ResponseGenerationAgent(llm)
        self.validation = ValidationAgent()
        self.judge_agent = LLMJudgeAgent()
        self.metrics = MetricsEvaluator()
        self.sql_tool = sql_tool
        self.pdf_tool = pdf_tool
        self.document_tool = document_tool
        self.rag = rag
        self.session_rag: dict[str, RagPipeline] = {}

    async def chat(self, request: ChatRequest) -> ChatResponse:
        usage = TokenUsage()
        token = usage_context.set(usage)
        events = []
        upstream = progress_sink.get()

        async def report(event):
            events.append(event)
            if upstream:
                await upstream(event)

        progress_token = progress_sink.set(report)
        try:
            try:
                response = await self._chat(request)
            except Exception:
                for event in list(events):
                    if event["status"] == "In Progress" and not any(e["step"] == event["step"] and e["status"] in {"Completed", "Failed"} for e in events[events.index(event)+1:]):
                        await progress(event["step"], "Failed", "Request failed")
                logging.getLogger(__name__).exception("Chat execution failed")
                response = ChatResponse(
                    status="error", answer="I could not complete this request because a service or data processing step failed. Please retry; your chat is still available.",
                    session_id=request.session_id, plan=ExecutionPlan(intent="request_failed"),
                    tool_results=[], citations=[], guardrails=GuardrailResult(allowed=True),
                    judge=JudgeResult(notes="Request failed; no answer evaluated."),
                    metrics=self.metrics.compute([], [], perf_counter()),
                    timeline=[{"agent": "orchestrator", "status": "error"}],
                )
            response.metrics.input_tokens = usage.input_tokens
            response.metrics.output_tokens = usage.output_tokens
            response.metrics.total_tokens = usage.input_tokens + usage.output_tokens
            response.metrics.llm_calls = usage.llm_calls
            response.metrics.tokens_estimated = usage.tokens_estimated
            response.timeline.extend(events)
            return response
        finally:
            usage_context.reset(token)
            progress_sink.reset(progress_token)

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        started = perf_counter()
        timeline: list[dict[str, object]] = []
        for step in ["Input checks", "Planning and tool selection", "Evidence validation", "Generate final answer"]:
            await progress(step, "Pending")
        await progress("Input checks", "In Progress", "Checking request safety and selecting relevant chat context")
        guardrail = self.guardrails.validate_input(request.query)
        timeline.append({"agent": "guardrail", "allowed": guardrail.allowed, "reasons": guardrail.reasons})
        if not guardrail.allowed:
            await progress("Input checks", "Failed", "Request blocked by input checks")
            plan = ExecutionPlan(intent="blocked")
            judge = await self.judge_agent.judge("Request blocked by guardrails.", [])
            metrics = self.metrics.compute([], [], started)
            return ChatResponse(
                answer="I cannot process that request because it appears to contain unsafe instructions.",
                session_id=request.session_id,
                plan=plan,
                tool_results=[],
                citations=[],
                guardrails=guardrail,
                judge=judge,
                metrics=metrics,
                timeline=timeline,
            )

        query = guardrail.masked_text or request.query
        pending = self.memory.pending.get(request.session_id)
        if pending:
            query = f"Original unresolved request: {pending}\nUser clarification: {query}"
        memory = self.memory.relevant(request.session_id, query)
        self.memory.add(request.session_id, ChatMessage(role="user", content=query))
        await progress("Input checks", "Completed")
        await progress("Planning and tool selection", "In Progress", "Determining required sources and tools")
        plan = await self.planner.plan(query, request.files, memory, automatic_mode=request.automatic_mode)
        if request.automatic_mode:
            plan.clarification_questions, plan.clarification_options = [], []
            # Read source requirements before generating database queries.
            plan.steps.sort(key=lambda step: step.tool == ToolName.sql)
        selected = [{"tool": step.tool.value, "purpose": step.reason} for step in plan.steps if step.tool != ToolName.direct]
        tool_mode = "No tools" if not selected else ("Single tool" if len(selected) == 1 else "Multiple tools")
        await progress("Planning and tool selection", "Completed", tool_mode, tools=selected, tool_mode=tool_mode)
        timeline.append({"agent": "planner", "plan": plan.model_dump()})

        results: list[ToolResult] = []
        for step in plan.steps:
            if step.tool != ToolName.direct:
                await progress(f"Tool: {step.tool.value}", "Pending", step.reason)
        for step in plan.steps:
            if plan.clarification_questions:
                break
            if step.tool == ToolName.direct:
                continue
            await progress(f"Tool: {step.tool.value}", "In Progress", step.reason)
            if step.tool == ToolName.sql and request.automatic_mode:
                result = await self.database_agent.answer(query, memory, results)
            elif step.tool == ToolName.rag and request.session_id in self.session_rag:
                result = await asyncio.to_thread(asyncio.run, self.session_rag[request.session_id].answer(query + "\n" + memory))
            else:
                # SQL templates must not interpret unrelated words or SELECT statements in old turns.
                tool_query = query if step.tool == ToolName.sql else query + "\nRelevant conversation:\n" + memory
                result = await self._execute_tool(step.tool, tool_query, request.files)
            results.append(result)
            await progress(f"Tool: {step.tool.value}", "Completed" if result.success else "Failed", step.reason if result.success else "Tool could not retrieve reliable evidence")
            timeline.append({"agent": f"{step.tool.value}_agent", "success": result.success, "latency_ms": result.latency_ms})

        await progress("Evidence validation", "In Progress", "Checking tool success and available evidence")
        validation_issues = self.validation.validate_tool_results(results)
        await progress("Evidence validation", "Failed" if validation_issues else "Completed", "Required evidence unavailable" if validation_issues else "Tool results checked")
        timeline.append({"agent": "validation", "issues": validation_issues})

        questions = plan.clarification_questions
        options = plan.clarification_options
        status = "answered"
        await progress("Generate final answer", "In Progress", "Assessing evidence, SQL intent and answer accuracy")
        if questions:
            answer = question_answer(questions, options)
        elif validation_issues:
            status = "error"
            answer = "The required data could not be retrieved. Please check the data source connection or uploaded file, then retry."
        else:
            assessment = await self.response_agent.assess(query, plan, results, memory, automatic_mode=request.automatic_mode)
            questions = assessment["clarification_questions"]
            answer = assessment["answer"]
            options = assessment.get("clarification_options", [])
            status = assessment.get("status", "answered")
        if request.automatic_mode:
            questions, options = [], []
            for result in results:
                if result.tool == ToolName.sql and result.success and isinstance(result.output, dict) and "row_count" in result.output:
                    output = result.output
                    answer += "\n\nGenerated SQL:\n```sql\n" + output["sql"] + "\n```"
                    answer += f"\n\nTotal rows: {output['row_count']} · Total columns: {output['column_count']}\n\nFirst 10 rows:\n"
                    columns = output["columns"]
                    def cell(value):
                        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ") if value is not None else "NULL"
                    answer += "| " + " | ".join(map(cell, columns)) + " |\n| " + " | ".join("---" for _ in columns) + " |\n"
                    answer += "\n".join("| " + " | ".join(cell(row[c]) for c in columns) + " |" for row in output["rows"])
                    if not output["rows"]:
                        answer += "\nNo rows matched the query."
                    if output.get("assumptions"):
                        answer += "\n\nAssumptions: " + json.dumps(output["assumptions"], ensure_ascii=False)
            self.memory.pending.pop(request.session_id, None)
        if questions:
            self.memory.pending[request.session_id] = query
        elif status == "answered":
            self.memory.pending.pop(request.session_id, None)
        output_guardrail = self.guardrails.validate_output(answer)
        citations = [citation for result in results for citation in result.citations]
        judge = await self.judge_agent.judge(answer, citations)
        metrics = self.metrics.compute(results, citations, started)
        self.memory.add(request.session_id, ChatMessage(role="assistant", content=answer))
        timeline.append({"agent": "judge", "scores": judge.model_dump()})
        await progress("Generate final answer", "Failed" if status == "error" else "Completed", status)

        return ChatResponse(
            status="needs_clarification" if questions else status,
            clarification_questions=questions,
            clarification_options=options,
            answer=output_guardrail.masked_text or answer,
            session_id=request.session_id,
            plan=plan,
            tool_results=results,
            citations=citations,
            guardrails=output_guardrail,
            judge=judge,
            metrics=metrics,
            timeline=timeline,
        )

    async def _execute_tool(self, tool: ToolName, query: str, files: list[str]) -> ToolResult:
        if tool == ToolName.sql:
            return await asyncio.to_thread(asyncio.run, self.sql_tool.answer(query))
        if tool == ToolName.pdf:
            return await asyncio.to_thread(asyncio.run, self.pdf_tool.answer(query, files))
        if tool == ToolName.document:
            return await asyncio.to_thread(asyncio.run, self.document_tool.answer(query, files))
        if tool == ToolName.rag:
            return await asyncio.to_thread(asyncio.run, self.rag.answer(query))
        raise ValueError(f"Unsupported tool: {tool}")
