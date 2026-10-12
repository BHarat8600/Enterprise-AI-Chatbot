from collections import defaultdict, deque
import re

from models.schemas import ChatMessage


class ConversationMemory:
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._short_term: dict[str, deque[ChatMessage]] = defaultdict(lambda: deque(maxlen=max_messages))
        self._summaries: dict[str, str] = {}
        self.pending: dict[str, str] = {}
        self._archive: dict[str, list[ChatMessage]] = defaultdict(list)

    def add(self, session_id: str, message: ChatMessage) -> None:
        self._short_term[session_id].append(message)
        self._archive[session_id].append(message)

    def relevant(self, session_id: str, query: str, budget: int = 6000) -> str:
        """Select whole turns locally, retaining older relevant facts without an LLM call."""
        stop = {"the", "a", "an", "is", "of", "to", "and", "in", "it", "for", "what"}
        def words(text: str) -> set[str]:
            return set(re.findall(r"\w+", text.lower())) - stop
        target = words(query)
        messages = self._archive[session_id]
        turns = [messages[i:i + 2] for i in range(0, len(messages), 2)]
        ranked = []
        for i, turn in enumerate(turns):
            text = "\n".join(f"{m.role}: {m.content}" for m in turn)
            score = len(target & words(text))
            if score or i == len(turns) - 1:
                ranked.append((score, i, text))
        selected = []
        for _, i, text in sorted(ranked, reverse=True):
            if len(text) <= budget:
                selected.append((i, text))
                budget -= len(text)
        return "\n".join(text for _, text in sorted(selected))

    def get_recent(self, session_id: str) -> list[ChatMessage]:
        return list(self._short_term[session_id])

    def summarize(self, session_id: str) -> str:
        messages = self.get_recent(session_id)
        summary = " ".join(f"{m.role}: {m.content[:160]}" for m in messages[-8:])
        self._summaries[session_id] = summary
        return summary

    def get_summary(self, session_id: str) -> str:
        return self._summaries.get(session_id, "")
