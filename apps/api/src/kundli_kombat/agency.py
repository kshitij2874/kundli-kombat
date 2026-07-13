import json
from dataclasses import dataclass
from datetime import date
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


FOOTER = "for reflection and fun, not fate."


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
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.435, 0.87),
}


@lru_cache
def _model_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=str(settings.deepseek_base_url),
    )


def _cost(response: object, model: str) -> UsageCost:
    usage = getattr(response, "usage", None)
    input_tokens = int(
        getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", 0) or 0
    )
    output_tokens = int(
        getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", 0) or 0
    )
    input_rate, output_rate = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    usd = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    return UsageCost(input_tokens, output_tokens, round(usd, 6))


def _fallback_plan(request: ReadingRequest) -> ManagerPlan:
    if request.kind == "oracle":
        steps = [
            "Check the question against safety rules",
            "Read only relevant chart evidence",
            "Review tone and evidence before sending",
        ]
    elif request.kind == "placement":
        steps = [
            "Find the selected placement",
            "Explain it in plain language",
            "Review evidence and tone",
        ]
    else:
        steps = [
            "Read today's strongest chart signals",
            "Turn them into one useful reflection",
            "Review evidence and safety",
        ]
    return ManagerPlan(steps=steps, risk="low")


def _manager_plan(request: ReadingRequest) -> tuple[ManagerPlan, UsageCost]:
    settings = get_settings()
    if not settings.agency_configured or not langfuse_authenticated():
        return _fallback_plan(request), UsageCost()
    with agent_step(
        "manager.plan",
        {
            "task": request.kind,
            "model": settings.deepseek_model,
            "provider": "deepseek",
            "playerId": request.playerId,
        },
    ) as step:
        try:
            response = _model_client().chat.completions.create(
                model=settings.deepseek_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the Desk Manager for Kundli Kombat. Produce a short, task-specific plan. "
                            "Delegate interpretation, enforce evidence from the supplied chart, and include a final review. "
                            "Describe process only: never name a planet, placement, aspect, or transit because chart details are not supplied to you. "
                            "For daily tasks, the supplied chart and currentDate are sufficient; never request another "
                            "date, time, or location. "
                            "Never give medical, legal, financial, pregnancy, or death predictions. "
                            "Return JSON only with this exact shape: "
                            '{"steps":["step 1","step 2"],"risk":"low"}. '
                            "steps must contain 2 to 4 strings and risk must be low, medium, or high."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "kind": request.kind,
                                "question": request.question,
                                "placement": request.placement,
                                "currentDate": date.today().isoformat(),
                                "chartSupplied": True,
                                "recentConversation": [
                                    turn.model_dump() for turn in request.history
                                ],
                            }
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                extra_body={"thinking": {"type": "disabled"}},
                metadata={
                    "langfuse_observation_name": "manager.plan",
                    "task": request.kind,
                    "playerId": request.playerId,
                    "provider": "deepseek",
                },
            )
            plan = ManagerPlan.model_validate_json(response.choices[0].message.content or "{}")
            unsupported_plan_terms = {
                "sun",
                "moon",
                "mercury",
                "venus",
                "mars",
                "jupiter",
                "saturn",
                "uranus",
                "neptune",
                "pluto",
                "rahu",
                "ketu",
                "aspect",
                "transit",
                "placement",
            }
            plan_text = " ".join(plan.steps).lower()
            if any(term in plan_text for term in unsupported_plan_terms):
                plan = _fallback_plan(request)
        except ValidationError:
            return _fallback_plan(request), UsageCost()
        cost = _cost(response, settings.deepseek_model)
        step.cost_usd = cost.usd
    return plan, cost


def _placements(request: ReadingRequest) -> list[dict[str, object]]:
    raw = request.chart.get("placements", [])
    if not isinstance(raw, list):
        return []
    return [
        item
        for item in raw
        if isinstance(item, dict) and {"planet", "sign", "longitude"} <= item.keys()
    ]


def _fallback_draft(
    request: ReadingRequest, placements: list[dict[str, object]]
) -> InterpreterDraft:
    chosen = placements[:2]
    if request.placement:
        matched = [
            item for item in placements if str(item["planet"]).lower() == request.placement.lower()
        ]
        chosen = matched[:1] or chosen
    names = [str(item["planet"]) for item in chosen] or ["Sun"]
    tone = {
        "comfort": "Take the gentler route today. Protect your attention before you promise it away.",
        "straight": "Your move today is simple: say the useful thing early, then stop over-explaining.",
        "roast": "Your brain has opened seventeen tabs. Close sixteen before calling it intuition.",
    }[request.tone]
    question = (
        "Start with the part you can control, then take one small next step. "
        if request.question
        else ""
    )
    return InterpreterDraft(
        text=f"{question}{tone}",
        evidencePlanets=names,
    )


def _interpreter_draft(
    request: ReadingRequest, plan: ManagerPlan
) -> tuple[InterpreterDraft, UsageCost]:
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
        "currentDate": date.today().isoformat(),
        "managerPlan": plan.steps,
        "placements": placements,
        "recentConversation": [turn.model_dump() for turn in request.history],
    }
    with agent_step(
        "interpreter.read",
        {
            "task": request.kind,
            "model": settings.deepseek_model,
            "provider": "deepseek",
            "playerId": request.playerId,
        },
    ) as step:
        try:
            response = _model_client().chat.completions.create(
                model=settings.deepseek_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Kundli Kombat's Interpreter. Write for a curious 10-year-old with no astrology background. "
                            "The primary text must explain everyday meaning only: feelings, choices, habits, relationships, school/work, or handling pressure. "
                            "Never name planets, zodiac signs, houses, aspects, transits, nakshatras, or degrees in text; those belong only in hidden evidencePlanets. "
                            "Every claim must be driven by a planet supplied in the chart and evidencePlanets must list those exact planet names. "
                            "Do not invent aspects or transits. "
                            "Tone may be comfort, straight, or playful roast; never insult the real person. "
                            "Write 2-4 short sentences and do not add a disclaimer."
                            " When recentConversation is supplied, answer the current question as a follow-up: "
                            "use only relevant prior context, do not repeat it mechanically, and never mix users."
                            " For a daily task, the supplied chart and currentDate are sufficient: always provide "
                            "a useful reflection and never ask the user for another date, time, or location. "
                            "Return JSON only with this exact shape: "
                            '{"text":"2-4 short sentences","evidencePlanets":["Sun","Moon"]}. '
                            "evidencePlanets must contain 1 to 4 exact planet names from the supplied placements."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
                response_format={"type": "json_object"},
                max_tokens=600,
                extra_body={"thinking": {"type": "disabled"}},
                metadata={
                    "langfuse_observation_name": "interpreter.read",
                    "task": request.kind,
                    "playerId": request.playerId,
                    "provider": "deepseek",
                },
            )
            draft = InterpreterDraft.model_validate_json(
                response.choices[0].message.content or "{}"
            )
        except ValidationError:
            return _fallback_draft(request, placements), UsageCost()
        cost = _cost(response, settings.deepseek_model)
        step.cost_usd = cost.usd
    return draft, cost


def _review(request: ReadingRequest, draft: InterpreterDraft) -> tuple[str, list[Evidence], bool]:
    placements = _placements(request)
    by_planet = {str(item["planet"]): item for item in placements}
    evidence = [
        Evidence(
            planet=name,
            sign=str(by_planet[name]["sign"]),
            longitude=float(by_planet[name]["longitude"]),
        )
        for name in draft.evidencePlanets
        if name in by_planet
    ]
    banned = ("will die", "definitely", "guaranteed", "buy the stock", "cure")
    planet_names = {
        "sun",
        "moon",
        "mercury",
        "venus",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
        "pluto",
        "rahu",
        "ketu",
    }
    astrology_jargon = planet_names | {
        "aries",
        "taurus",
        "gemini",
        "cancer",
        "leo",
        "virgo",
        "libra",
        "scorpio",
        "sagittarius",
        "capricorn",
        "aquarius",
        "pisces",
        "aspect",
        "transit",
        "orb",
        "nakshatra",
        "retrograde",
        "sidereal",
        "ayanamsa",
    }
    cited_planets = {name for name in planet_names if name in draft.text.lower()}
    evidence_planets = {name.lower() for name in draft.evidencePlanets}
    supplied_planets = {name.lower() for name in by_planet}
    valid = (
        bool(evidence)
        and cited_planets <= evidence_planets <= supplied_planets
        and not any(term in draft.text.lower() for term in astrology_jargon)
        and not any(term in draft.text.lower() for term in banned)
    )
    text = draft.text.strip()
    if not text.lower().endswith(FOOTER.lower()):
        text = f"{text} {FOOTER}"
    return text, evidence, valid


async def _store_escalation(request: ReadingRequest, decision: PolicyDecision) -> None:
    try:
        args = {
            "question": request.question or "",
            "policy": decision.policy,
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
                readingId=f"local-{uuid4().hex}",
                kind=request.kind,
                text=decision.response or FOOTER,
                evidence=[],
                refused=True,
                policy=decision.policy,
                plan=["Safety screen", "Warm refusal", "Escalation recorded"],
                traceId=trace.trace_id,
                traceExported=trace.exported,
                latencyMs=trace.latency_ms,
                costUsd=0,
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
        readingId=reading_id,
        kind=request.kind,
        text=text,
        evidence=evidence,
        refused=False,
        policy=None,
        plan=plan.steps,
        traceId=trace.trace_id,
        traceExported=trace.exported,
        latencyMs=trace.latency_ms,
        costUsd=cost,
    )
