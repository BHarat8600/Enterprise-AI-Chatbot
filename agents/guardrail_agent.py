import re

from models.schemas import GuardrailResult


class GuardrailAgent:
    name = "guardrail"

    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"developer\s+message",
        r"system\s+prompt",
        r"jailbreak",
        r"disable\s+safety",
    ]
    pii_patterns = {
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "phone": r"\b(?:\+?\d[\d -]{8,}\d)\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    }

    def validate_input(self, text: str) -> GuardrailResult:
        reasons = [
            f"Potential prompt injection: {pattern}"
            for pattern in self.injection_patterns
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        masked = text
        for label, pattern in self.pii_patterns.items():
            masked = re.sub(pattern, f"[MASKED_{label.upper()}]", masked)
        return GuardrailResult(allowed=not reasons, reasons=reasons, masked_text=masked)

    def validate_output(self, text: str) -> GuardrailResult:
        if "I made this up" in text:
            return GuardrailResult(allowed=False, reasons=["Output admits unsupported fabrication"])
        return GuardrailResult(allowed=True, masked_text=text)

