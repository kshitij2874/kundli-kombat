import json
import secrets
from datetime import date
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from .agency import UsageCost, _cost, _model_client
from .battle_math import ScoredRound, score_battle
from .battle_stats import fighter_stats
from .config import get_settings
from .convex_client import ConvexUnavailable, mutation
from .ephemeris import calculate_chart
from .models import BattleRequest, BattleResponse, BattleRound, CelebritySummary
from .observability import agent_step, langfuse_authenticated, traced_task


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "celebrities.json"


class RefereeDraft(BaseModel):
    lines: list[str] = Field(min_length=5, max_length=5)
    prediction: str = Field(min_length=10, max_length=180)


def _seeds() -> list[dict[str, object]]:
    return json.loads(DATA_PATH.read_text())


def _celebrity_chart(name: str) -> tuple[dict[str, object], dict[str, object]]:
    seed = next((item for item in _seeds() if item["name"] == name), None)
    if seed is None:
        raise ValueError(f"Unknown celebrity: {name}")
    chart = calculate_chart(
        dob=date.fromisoformat(str(seed["dob"])),
        tob=None,
        tob_unknown=True,
        lat=float(seed["lat"]),
        lon=float(seed["lon"]),
        tz=str(seed["tz"]),
    )
    return seed, chart


def list_celebrities() -> list[CelebritySummary]:
    result = []
    for seed in _seeds():
        _, chart = _celebrity_chart(str(seed["name"]))
        result.append(
            CelebritySummary(
                name=str(seed["name"]),
                place=str(seed["place"]),
                dob=str(seed["dob"]),
                big3={key: str(value) for key, value in chart["big3"].items()},
                stats=fighter_stats(chart),
            )
        )
    return result


def _fallback_referee(rounds: list[ScoredRound], opponent: str, tone: str) -> RefereeDraft:
    icons = {"Love": "❤️", "Career": "💼", "Luck": "🍀", "Fire": "🔥", "Chaos": "🌀"}
    lines = []
    for item in rounds:
        if item.p1_score == item.p2_score:
            result = "Dead even—the cosmos refuses to pick a side."
        elif item.p1_score > item.p2_score:
            result = f"You take it {item.p1_score} to {item.p2_score}. Cosmic flex confirmed."
        else:
            result = (
                f"{opponent} takes it {item.p2_score} to {item.p1_score}. That one left a crater."
            )
        lines.append(f"{icons[item.name]} {result}")
    prediction = f"Five rounds down: you and {opponent} just gave the cosmos a proper main event."
    if tone == "savage":
        prediction = (
            f"You and {opponent} could turn choosing a restaurant into a three-act cosmic trial."
        )
    return RefereeDraft(lines=lines, prediction=prediction)


def _referee(
    rounds: list[ScoredRound], opponent: str, tone: str, player_id: str
) -> tuple[RefereeDraft, UsageCost]:
    settings = get_settings()
    fallback = _fallback_referee(rounds, opponent, tone)
    if not settings.agency_configured or not langfuse_authenticated():
        return fallback, UsageCost()
    with agent_step(
        "referee.narrate",
        {
            "task": "battle",
            "model": settings.deepseek_model,
            "provider": "deepseek",
            "opponent": opponent,
            "playerId": player_id,
        },
    ) as step:
        try:
            response = _model_client().chat.completions.create(
                model=settings.deepseek_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the Oracle Commentator. Narrate exactly five supplied deterministic rounds in order: Love, Career, Luck, Fire, Chaos. "
                            "Do not alter or invent numbers. Roast only the chart matchup, never the real people or personal facts. "
                            "Each line must name the round winner and both exact scores in one punchy, playful sentence. "
                            "End with one harmless one-line cosmic verdict. Return JSON only with this exact shape: "
                            '{"lines":["round 1","round 2","round 3","round 4","round 5"],"prediction":"verdict"}.'
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "opponent": opponent,
                                "tone": tone,
                                "rounds": [
                                    {
                                        "name": item.name,
                                        "p1": item.p1_score,
                                        "p2": item.p2_score,
                                        "aspects": item.aspects,
                                    }
                                    for item in rounds
                                ],
                            }
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=600,
                extra_body={"thinking": {"type": "disabled"}},
                metadata={
                    "langfuse_observation_name": "referee.narrate",
                    "task": "battle",
                    "playerId": player_id,
                    "provider": "deepseek",
                },
            )
            draft = RefereeDraft.model_validate_json(response.choices[0].message.content or "{}")
        except ValidationError:
            return fallback, UsageCost()
        cost = _cost(response, settings.deepseek_model)
        step.cost_usd = cost.usd
    return draft, cost


async def battle(request: BattleRequest) -> BattleResponse:
    if request.celebrity:
        _, p2_chart = _celebrity_chart(request.celebrity)
        opponent = request.celebrity
    elif request.p2Chart and request.p2Id:
        p2_chart, opponent = request.p2Chart, request.p2Name or "Friend"
    else:
        raise ValueError("A celebrity or second player chart is required")
    with traced_task("manager.battle", task="battle", player_id=request.p1Id) as trace:
        with agent_step("chart.match", {"deterministic": True}):
            scored, verdict, winner = score_battle(request.p1Chart, p2_chart)
        narration, cost = _referee(scored, opponent, request.tone, request.p1Id)
        rounds = [
            BattleRound(
                name=item.name,
                p1Score=item.p1_score,
                p2Score=item.p2_score,
                compatibilityScore=item.compatibility_score,
                line=narration.lines[index],
                aspects=list(item.aspects),
            )
            for index, item in enumerate(scored)
        ]
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(4))
        args = {
            "code": code,
            "p1Id": request.p1Id,
            "celebrity": request.celebrity,
            "rounds": [item.model_dump() for item in rounds],
            "verdictPct": verdict,
            "prediction": narration.prediction,
            "latencyMs": trace.latency_ms,
            "costUsd": cost.usd,
            "langfuseTraceId": trace.trace_id,
        }
        if isinstance(args.get("p2Id"), str) and str(args["p2Id"]).startswith("local-"):
            args.pop("p2Id")
        try:
            stored = await mutation(
                "battles:create", {key: value for key, value in args.items() if value is not None}
            )
            battle_id, card_id = str(stored["battleId"]), str(stored["cardId"])
        except ConvexUnavailable:
            battle_id, card_id = f"local-{uuid4().hex}", f"local-{uuid4().hex}"
    return BattleResponse(
        battleId=battle_id,
        code=code,
        opponent=opponent,
        rounds=rounds,
        verdictPct=verdict,
        prediction=narration.prediction,
        winner=winner,
        cardId=card_id,
        traceId=trace.trace_id,
        traceExported=trace.exported,
        latencyMs=trace.latency_ms,
        costUsd=cost.usd,
    )
