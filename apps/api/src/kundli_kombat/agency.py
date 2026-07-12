import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from uuid import uuid4

from langfuse.openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from .config import get_settings
from .convex_client import ConvexUnavailable, mutation
from .models import Evidence, ReadingRequest, ReadingResponse
from .observability import agent_step, langfuse_authenticated, traced_task
from .policy import PolicyDecision, screen_question


FOOTER = "For reflection and fun, not fate."


class ManagerPlan(BaseModel):
    steps: list[str] = Field(min_length=2, max_length=4)
    risk: Literal["low", "medium", "high"]


class InterpreterDraft(BaseModel):
    text: str = Field(min_length=20, max_length=1200)
    evidencePlanets: list[str] = Field(min_length=1, max_length=4)


@dataclass(frozen=True)
class UsageCost:
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0


PRICES_PER_MTOK = {
    "gpt-5.6-sol": (5.0, 30.0),
    "gpt-5-mini": (0.25, 2.0),
}


@lru_cache
def _openai_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def _cost(response: object, model: str) -> UsageCost:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    input_rate, output_rate = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    usd = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    return UsageCost(input_tokens, output_tokens, round(usd, 6))


def _fallback_plan(request: ReadingRequest) -> ManagerPlan:
    if request.kind == "oracle":
        steps = ["Check the question against safety rules", "Read only relevant chart evidence", "Review tone and evidence before sending"]
    elif request.kind == "placement":
        steps = ["Find the selected placement", "Explain it in plain language", "Review evidence and tone"]
    else:
        steps = ["Read today's strongest chart signals", "Turn them into one useful reflection", "Review evidence and safety"]
    return ManagerPlan(steps=steps, risk="low")


def _manager_plan(request: ReadingRequest) -> tuple[ManagerPlan, UsageCost]:
    settings = get_settings()
    if not settings.agency_configured or not langfuse_authenticated():
        return _fallback_plan(request), UsageCost()
    with agent_step("manager.plan", {"task": request.kind, "model": settings.openai_sol_model}):
        try:
            response = _openai_client().responses.parse(
                model=settings.openai_sol_model,
                instructions=(
                    "You are the Desk Manager for Kundli Kombat. Produce a short, task-specific plan. "
                    "Delegate interpretation, enforce evidence from the supplied chart, and include a final review. "
                    "Never give medical, legal, financial, pregnancy, or death predictions."
                ),
                input=json.dumps({"kind": request.kind, "question": request.question, "placement": request.placement}),
                text_format=ManagerPlan,
                reasoning={"effort": "low"},
                max_output_tokens=500,
                metadata={"langfuse_observation_name": "manager.plan", "task": request.kind},
            )
        except ValidationError:
            return _fallback_plan(request), UsageCost()
    return response.output_parsed or _fallback_plan(request), _cost(response, settings.openai_sol_model)


def _placements(request: ReadingRequest) -> list[dict[str, object]]:
    raw = request.chart.get("placements", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and {"planet", "sign", "longitude"} <= item.keys()]


def _fallback_draft(request: ReadingRequest, placements: list[dict[str, object]]) -> InterpreterDraft:
    chosen = placements[:2]
    if request.placement:
        matched = [item for item in placements if str(item["planet"]).lower() == request.placement.lower()]
        chosen = matched[:1] or chosen
    names = [str(item["planet"]) for item in chosen] or ["Sun"]
    evidence_phrase = " and ".join(f"your {item['planet']} in {item['sign']}" for item in chosen)
    tone = {
        "comfort": "Take the gentler route today: protect your attention before you promise it away.",
        "straight": "Your move today is simple: say the useful thing early, then stop over-explaining.",
        "roast": "Your chart has opened seventeen mental tabs; close sixteen before calling it intuition.",
    }[request.tone]
    question = f" For your question, “{request.question}”," if request.question else ""
    return InterpreterDraft(
        text=f"With {evidence_phrase},{question} {tone}",
        evidencePlanets=names,
    )


def _interpreter_draft(request: ReadingRequest, plan: ManagerPlan) -> tuple[InterpreterDraft, UsageCost]:
    settings = get_settings()
    placements = _placements(request)
    if not settings.agency_configured or not langfuse_authenticated():
        return _fallback_draft(request, placements), UsageCost()
    payload = {
        "task": request.kind,
        "question": request.question,
        "placement": request.placement,
        "tone": request.tone,
        "language": request.lang,
        "managerPlan": plan.steps,
        "placements": placements,
    }
    with agent_step("interpreter.read", {"task": request.kind, "model": settings.openai_sol_model}):
        try:
            response = _openai_client().responses.parse(
                model=settings.openai_sol_model,
                instructions=(
                    "You are Kundli Kombat's Interpreter. Use plain language, no astrology jargon. "
                    "Every claim must be driven by a planet supplied in the chart and evidencePlanets must list those exact planet names. "
                    "Tone may be comfort, straight, or playful roast; never insult the real person. "
                    "Write 2-4 short sentences and do not add a disclaimer."
                ),
                input=json.dumps(payload),
                text_format=InterpreterDraft,
                reasoning={"effort": "low"},
                max_output_tokens=600,
                metadata={"langfuse_observation_name": "interpreter.read", "task": request.kind},
            )
        except ValidationError:
            return _fallback_draft(request, placements), UsageCost()
    return response.output_parsed or _fallback_draft(request, placements), _cost(response, settings.openai_sol_model)


def _review(request: ReadingRequest, draft: InterpreterDraft) -> tuple[str, list[Evidence], bool]:
    placements = _placements(request)
    by_planet = {str(item["planet"]): item for item in placements}
    evidence = [
        Evidence(planet=name, sign=str(by_planet[name]["sign"]), longitude=float(by_planet[name]["longitude"]))
        for name in draft.evidencePlanets if name in by_planet
    ]
    banned = ("will die", "definitely", "guaranteed", "buy the stock", "cure")
    valid = bool(evidence) and not any(term in draft.text.lower() for term in banned)
    text = draft.text.strip()
    if not text.lower().endswith(FOOTER.lower()):
        text = f"{text} {FOOTER}"
    return text, evidence, valid


async def _store_escalation(request: ReadingRequest, decision: PolicyDecision) -> None:
    try:
        args = {
            "question": request.question or "",
            "policy": "medical" if decision.policy == "under13" else decision.policy,
            "context": {"kind": request.kind, "tone": request.tone},
        }
        if not request.playerId.startswith("local-"):
            args["playerId"] = request.playerId
        await mutation("escalations:create", args)
    except ConvexUnavailable:
        return


async def create_reading(request: ReadingRequest) -> ReadingResponse:
    with traced_task("manager.task", task=request.kind, player_id=request.playerId) as trace:
        with agent_step("sentinel.screen", {"task": request.kind}):
            decision = screen_question(request.question)
        if decision.refused:
            await _store_escalation(request, decision)
            return ReadingResponse(
                readingId=f"local-{uuid4().hex}", kind=request.kind,
                text=decision.response or FOOTER, evidence=[], refused=True, policy=decision.policy,
                plan=["Safety screen", "Warm refusal", "Escalation recorded"],
                traceId=trace.trace_id, traceExported=trace.exported,
                latencyMs=trace.latency_ms, costUsd=0,
            )

        plan, manager_cost = _manager_plan(request)
        draft, interpreter_cost = _interpreter_draft(request, plan)
        with agent_step("manager.review", {"task": request.kind}):
            text, evidence, valid = _review(request, draft)
        if not valid:
            draft = _fallback_draft(request, _placements(request))
            text, evidence, valid = _review(request, draft)
        if not valid:
            raise ValueError("Interpreter output failed evidence review")
        cost = round(manager_cost.usd + interpreter_cost.usd, 6)
        reading_args = {
            "playerId": request.playerId,
            "kind": request.kind,
            "tone": request.tone,
            "text": text,
            "evidence": [item.model_dump() for item in evidence],
            "latencyMs": trace.latency_ms,
            "costUsd": cost,
            "langfuseTraceId": trace.trace_id,
        }
        if request.question:
            reading_args["question"] = request.question
        try:
            reading_id = str(await mutation("readings:create", reading_args))
        except ConvexUnavailable:
            reading_id = f"local-{uuid4().hex}"
    return ReadingResponse(
        readingId=reading_id, kind=request.kind, text=text, evidence=evidence,
        refused=False, policy=None, plan=plan.steps, traceId=trace.trace_id,
        traceExported=trace.exported, latencyMs=trace.latency_ms, costUsd=cost,
    )
