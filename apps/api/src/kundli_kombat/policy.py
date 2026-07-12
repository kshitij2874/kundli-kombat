import re
from dataclasses import dataclass
from typing import Literal


Policy = Literal["doom", "medical", "financial", "abuse", "under13"]


@dataclass(frozen=True)
class PolicyDecision:
    refused: bool
    policy: Policy | None = None
    response: str | None = None


RULES: tuple[tuple[Policy, re.Pattern[str]], ...] = (
    ("doom", re.compile(r"\b(when|how|will)\b.{0,30}\b(die|death|dead|killed)\b", re.I)),
    ("medical", re.compile(r"\b(surgery|cancer|diagnos|pregnan|medicine|doctor|health|illness)\b", re.I)),
    ("financial", re.compile(r"\b(stock|crypto|invest|loan|bankrupt|financial advice|buy|sell)\b", re.I)),
    ("abuse", re.compile(r"\b(hit me|hurt me|abuse|unsafe at home|violence)\b", re.I)),
    ("under13", re.compile(r"\b(i am|i'm|age)\s+(?:[0-9]|1[0-2])\b", re.I)),
)


def screen_question(question: str | None) -> PolicyDecision:
    if not question:
        return PolicyDecision(refused=False)
    lowered = question.lower()
    if "ignore" in lowered and any(word in lowered for word in ("rules", "system", "doctor", "policy")):
        return PolicyDecision(
            refused=True,
            policy="medical",
            response="I can’t step outside the safety rules or act as a professional. I can keep this reflective and playful instead — for reflection and fun, not fate.",
        )
    for policy, pattern in RULES:
        if pattern.search(question):
            support = {
                "doom": "I can’t predict death or frightening outcomes. If this fear feels immediate, please reach out to someone you trust or a qualified support service.",
                "medical": "I can’t predict medical outcomes or replace a qualified clinician. I can help you frame questions for your care team.",
                "financial": "I can’t tell you what to buy, sell, or risk. A qualified financial adviser can work from your real circumstances.",
                "abuse": "I’m sorry you’re dealing with this. Astrology isn’t the right tool for safety; contact local emergency services or a trusted person if you may be in danger.",
                "under13": "This experience is for people aged 13 and over. Please ask a parent or guardian to explore it with you.",
            }[policy]
            return PolicyDecision(
                refused=True,
                policy=policy,
                response=f"{support} For reflection and fun, not fate.",
            )
    return PolicyDecision(refused=False)

