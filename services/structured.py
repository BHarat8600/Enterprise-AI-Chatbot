import json


def json_object(raw: str) -> dict:
    """Accept fenced JSON, but reject arrays/scalars and malformed model output."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def clarifications(data: dict) -> tuple[list[str], list[dict]]:
    questions = data.get("clarification_questions", [])
    if not isinstance(questions, list):
        raise ValueError("Expected a question list")
    texts, choices = [], []
    for item in questions[:3]:
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())
        elif isinstance(item, dict):
            question = item.get("question")
            options = item.get("options", [])
            if not isinstance(question, str) or not question.strip():
                raise ValueError("Invalid question")
            if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
                raise ValueError("Invalid options")
            options = list(dict.fromkeys(o.strip() for o in options if o.strip()))[:5]
            texts.append(question.strip())
            choices.append({"question": question.strip(), "options": options})
        else:
            raise ValueError("Invalid clarification")
    return texts, choices


def question_answer(questions: list[str], choices: list[dict]) -> str:
    lines = ["Please clarify:"]
    for question in questions:
        lines.append(f"- {question}")
        for choice in choices:
            if choice["question"] == question:
                lines.extend(f"  {i}. {option}" for i, option in enumerate(choice["options"], 1))
    return "\n".join(lines)
