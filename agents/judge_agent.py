from models.schemas import JudgeResult, SourceCitation


class LLMJudgeAgent:
    name = "llm_judge"

    async def judge(self, answer: str, citations: list[SourceCitation]) -> JudgeResult:
        grounded = 0.8 if citations else 0.4
        relevance = 0.8 if answer.strip() else 0.0
        hallucination = max(0.0, 1.0 - grounded)
        return JudgeResult(
            correctness=grounded,
            groundedness=grounded,
            faithfulness=grounded,
            completeness=0.7 if answer else 0.0,
            relevance=relevance,
            hallucination_score=hallucination,
            notes="Heuristic judge active. Configure an LLM judge provider for deeper scoring.",
        )

