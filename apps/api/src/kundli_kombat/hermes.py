from __future__ import annotations

import hashlib
import json
from datetime import date, time
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .agency import FOOTER, create_reading
from .battles import battle, list_celebrities
from .config import get_settings
from .convex_client import ConvexUnavailable, mutation, query
from .geocoding import search_places
from .models import BattleRequest, OnboardRequest, ReadingRequest
from .observability import langfuse_authenticated, traced_task
from .onboarding import onboard


Action = Literal["status", "help", "onboard", "daily", "oracle", "celebrity_battle"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HermesIdentity(StrictModel):
    channel: Literal["telegram"]
    chatId: str = Field(min_length=1, max_length=100)
    userId: str = Field(min_length=1, max_length=100)
    threadId: str | None = Field(default=None, max_length=100)


class HermesRequest(StrictModel):
    version: Literal["1"]
    requestId: UUID
    action: Action
    identity: HermesIdentity
    playerId: str | None = Field(default=None, max_length=100)
    input: dict[str, Any]


class EmptyInput(StrictModel):
    pass


class OnboardInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    birthDate: date
    localBirthTime: time | None
    birthTimeUnknown: bool
    birthPlace: str = Field(min_length=2, max_length=160)
    tone: Literal["comfort", "straight", "roast"]
    language: Literal["en", "hinglish"]

    @model_validator(mode="after")
    def validate_birth_time(self) -> "OnboardInput":
        if self.birthDate > date.today():
            raise ValueError("birthDate must not be in the future")
        if self.birthTimeUnknown and self.localBirthTime is not None:
            raise ValueError("localBirthTime must be null when birthTimeUnknown is true")
        if not self.birthTimeUnknown and self.localBirthTime is None:
            raise ValueError("localBirthTime is required when birthTimeUnknown is false")
        if self.localBirthTime and (self.localBirthTime.second or self.localBirthTime.microsecond):
            raise ValueError("localBirthTime must use minute precision")
        return self


class DailyInput(StrictModel):
    tone: Literal["comfort", "straight", "roast"]
    language: Literal["en", "hinglish"]


class OracleInput(DailyInput):
    question: str = Field(min_length=1, max_length=800)


class BattleInput(StrictModel):
    celebrity: str = Field(min_length=1, max_length=100)
    tone: Literal["friendly", "savage"]
    language: Literal["en", "hinglish"]


INPUT_MODELS: dict[Action, type[StrictModel]] = {
    "status": EmptyInput,
    "help": EmptyInput,
    "onboard": OnboardInput,
    "daily": DailyInput,
    "oracle": OracleInput,
    "celebrity_battle": BattleInput,
}

POLICY_NAMES = {
    "doom": "death",
    "medical": "health",
    "pregnancy": "pregnancy",
    "legal": "legal",
    "financial": "financial_doom",
    "abuse": "abuse",
    "prompt_injection": "prompt_injection",
    "under13": "under13",
}


class HermesFailure(RuntimeError):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details


def _fingerprint(request: HermesRequest) -> str:
    payload = request.model_dump(mode="json")
    payload.pop("requestId", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _with_footer(message: str) -> str:
    clean = message.strip()
    if clean.lower().endswith(FOOTER):
        return f"{clean[:-len(FOOTER)]}{FOOTER}"
    return f"{clean} {FOOTER}"


def _meta(trace_id: str, exported: bool, latency_ms: int, cost_usd: float = 0) -> dict[str, Any]:
    return {
        "traceId": trace_id,
        "traceExported": exported,
        "latencyMs": max(0, latency_ms),
        "costUsd": max(0, cost_usd),
    }


def _success(
    request: HermesRequest,
    *,
    player_id: str | None,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any],
    refused: bool = False,
    policy: str | None = None,
) -> dict[str, Any]:
    return {
        "version": "1",
        "requestId": str(request.requestId),
        "ok": True,
        "action": request.action,
        "playerId": player_id,
        "message": message,
        "data": data,
        "safety": {"refused": refused, "policy": policy},
        "meta": meta,
        "error": None,
    }


def _error(
    payload: dict[str, Any], failure: HermesFailure, *, action: str | None = None,
) -> dict[str, Any]:
    return {
        "version": "1",
        "requestId": str(payload.get("requestId", "invalid-request")),
        "ok": False,
        "action": action or str(payload.get("action", "status")),
        "playerId": None,
        "message": failure.message,
        "data": {},
        "safety": {"refused": False, "policy": None},
        "meta": _meta(f"local-{uuid4().hex}", False, 0),
        "error": {
            "code": failure.code,
            "message": failure.message,
            "retryable": failure.retryable,
            "details": failure.details,
        },
    }


async def _identity_record(request: HermesRequest) -> dict[str, Any] | None:
    try:
        record = await query(
            "hermes:getIdentity",
            {"channel": "telegram", "userId": request.identity.userId},
        )
    except ConvexUnavailable as exc:
        raise HermesFailure(
            503, "SERVICE_UNAVAILABLE", "Player memory is temporarily unavailable.",
            retryable=True,
        ) from exc
    if request.playerId and (
        not record or str(record.get("playerId")) != request.playerId
    ):
        raise HermesFailure(
            409,
            "PLAYER_IDENTITY_MISMATCH",
            "That player does not belong to this Telegram identity. Run status to recover it.",
        )
    return record if isinstance(record, dict) else None


async def _require_player(request: HermesRequest) -> tuple[str, dict[str, Any]]:
    record = await _identity_record(request)
    if not record or not isinstance(record.get("player"), dict):
        raise HermesFailure(
            404, "PLAYER_NOT_FOUND", "Please onboard before requesting this Kundli task."
        )
    return str(record["playerId"]), record["player"]


async def _existing_request(request: HermesRequest, fingerprint: str) -> dict[str, Any] | None:
    try:
        existing = await query("hermes:getRequest", {"requestId": str(request.requestId)})
    except ConvexUnavailable:
        return None
    if not existing:
        return None
    if existing.get("fingerprint") != fingerprint:
        raise HermesFailure(
            409, "REQUEST_ID_CONFLICT", "That request ID was already used for different input."
        )
    response = existing.get("response")
    if isinstance(response, dict):
        meta = response.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("latencyMs"), (int, float)):
            meta["latencyMs"] = round(meta["latencyMs"])
        return response
    return None


async def _remember_request(
    request: HermesRequest, fingerprint: str, response: dict[str, Any]
) -> None:
    try:
        await mutation(
            "hermes:storeRequest",
            {
                "requestId": str(request.requestId),
                "fingerprint": fingerprint,
                "response": response,
            },
        )
    except ConvexUnavailable:
        return


async def _bind_player(request: HermesRequest, player_id: str) -> None:
    args: dict[str, Any] = {
        "channel": "telegram",
        "userId": request.identity.userId,
        "chatId": request.identity.chatId,
        "playerId": player_id,
    }
    if request.identity.threadId is not None:
        args["threadId"] = request.identity.threadId
    try:
        await mutation("hermes:bindIdentity", args)
    except ConvexUnavailable as exc:
        raise HermesFailure(
            503, "SERVICE_UNAVAILABLE", "The chart was created but player memory could not be linked. Please retry status.",
            retryable=True,
        ) from exc


def _age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


async def _under13_refusal(request: HermesRequest, value: OnboardInput) -> dict[str, Any]:
    try:
        await mutation(
            "escalations:create",
            {
                "question": "Telegram onboarding indicates an age under 13",
                "policy": "under13",
                "context": {"source": "telegram", "action": "onboard"},
            },
        )
    except ConvexUnavailable:
        pass
    with traced_task("sentinel.hermes", task="hermes.onboard", player_id=request.identity.userId) as trace:
        message = _with_footer(
            "This experience is for people aged 13 and over. Please ask a parent or guardian to explore it with you."
        )
    return _success(
        request,
        player_id=None,
        message=message,
        data={},
        refused=True,
        policy="under13",
        meta=_meta(trace.trace_id, trace.exported, trace.latency_ms),
    )


async def _onboard(request: HermesRequest, value: OnboardInput) -> dict[str, Any]:
    if _age_on(value.birthDate, date.today()) < 13:
        return await _under13_refusal(request, value)
    try:
        places = await search_places(value.birthPlace)
    except Exception as exc:
        raise HermesFailure(
            502, "UPSTREAM_UNAVAILABLE", "Birth-place lookup is temporarily unavailable.",
            retryable=True,
        ) from exc
    if not places.results:
        raise HermesFailure(
            422,
            "PLACE_NOT_FOUND",
            "I could not resolve that birthplace. Please send a city and country.",
            details={"suggestions": places.suggestions},
        )
    place = places.results[0]
    result = await onboard(
        OnboardRequest(
            name=value.name,
            dob=value.birthDate,
            tob=value.localBirthTime,
            tobUnknown=value.birthTimeUnknown,
            place=place.label,
            lat=place.lat,
            lon=place.lon,
            tz=place.timezone,
            tone=value.tone,
            lang=value.language,
            source="telegram",
        )
    )
    await _bind_player(request, result.playerId)
    notice = result.timeNotice
    if result.chartMode == "solar":
        notice = "Birth time unknown: this approximate noon solar chart does not claim a rising sign or houses."
    big3 = result.big3
    message = _with_footer(
        f"{result.identityLine} Sun: {big3['sun']} · Moon: {big3['moon']} · "
        f"Rising: {big3['rising']} · Nakshatra: {result.nakshatra}."
        + (f" {notice}" if notice else "")
    )
    return _success(
        request,
        player_id=result.playerId,
        message=message,
        data={
            "identityLine": result.identityLine,
            "big3": result.big3,
            "nakshatra": result.nakshatra,
            "chartMode": result.chartMode,
            "timeNotice": notice,
            "evidence": [item.model_dump(mode="json") for item in result.evidence],
        },
        meta=_meta(result.traceId, result.traceExported, result.latencyMs),
    )


async def _reading(
    request: HermesRequest, value: DailyInput | OracleInput
) -> dict[str, Any]:
    player_id, player = await _require_player(request)
    result = await create_reading(
        ReadingRequest(
            playerId=player_id,
            kind="oracle" if request.action == "oracle" else "daily",
            chart=player["chart"],
            question=value.question if isinstance(value, OracleInput) else None,
            tone=value.tone,
            lang=value.language,
        )
    )
    return _success(
        request,
        player_id=player_id,
        message=_with_footer(result.text),
        data={
            "readingId": result.readingId,
            "kind": result.kind,
            "evidence": [item.model_dump(mode="json") for item in result.evidence],
            "plan": result.plan,
        },
        refused=result.refused,
        policy=POLICY_NAMES.get(result.policy) if result.policy else None,
        meta=_meta(result.traceId, result.traceExported, result.latencyMs, result.costUsd),
    )


async def _battle(request: HermesRequest, value: BattleInput) -> dict[str, Any]:
    player_id, player = await _require_player(request)
    names = [item.name for item in list_celebrities()]
    if value.celebrity not in names:
        raise HermesFailure(
            422,
            "CELEBRITY_NOT_FOUND",
            "Choose one of the available celebrity opponents.",
            details={"celebrities": names},
        )
    result = await battle(
        BattleRequest(
            p1Id=player_id,
            p1Chart=player["chart"],
            celebrity=value.celebrity,
            tone=value.tone,
        )
    )
    round_lines = "\n".join(
        f"{item.name}: {item.p1Score}–{item.p2Score}. {item.line}" for item in result.rounds
    )
    message = _with_footer(
        f"You vs {result.opponent}: {result.verdictPct}% compatibility.\n"
        f"{round_lines}\nPrediction: {result.prediction}"
    )
    return _success(
        request,
        player_id=player_id,
        message=message,
        data=result.model_dump(
            mode="json",
            exclude={"traceId", "traceExported", "latencyMs", "costUsd"},
        ),
        meta=_meta(result.traceId, result.traceExported, result.latencyMs, result.costUsd),
    )


async def _status_or_help(request: HermesRequest) -> dict[str, Any]:
    record = await _identity_record(request)
    player_id = str(record["playerId"]) if record else None
    settings = get_settings()
    with traced_task(
        f"manager.hermes.{request.action}",
        task=f"hermes.{request.action}",
        player_id=player_id or request.identity.userId,
    ) as trace:
        if request.action == "status":
            message = (
                "Kundli Kombat is ready. Your chart is connected."
                if player_id else
                "Kundli Kombat is ready. Share your birth details to onboard."
            )
            data = {
                "service": "kundli-kombat-agency",
                "agencyReady": bool(settings.openai_api_key and langfuse_authenticated()),
                "hasPlayer": bool(player_id),
                "capabilities": ["onboard", "daily", "oracle", "celebrity_battle"],
            }
        else:
            message = (
                "Kundli Kombat can onboard your chart, give a daily reading, answer an Oracle "
                "question, or battle your chart against a celebrity. Tell me which one you want."
            )
            data = {
                "commands": [
                    {"action": "onboard", "usage": "Share name, birth date, local birth time (or unknown), and birth place."},
                    {"action": "daily", "usage": "Ask for today's reading after onboarding."},
                    {"action": "oracle", "usage": "Ask a question and choose comfort, straight, or roast tone."},
                    {"action": "celebrity_battle", "usage": "Choose a listed celebrity and friendly or savage tone."},
                ]
            }
    return _success(
        request,
        player_id=player_id,
        message=message,
        data=data,
        meta=_meta(trace.trace_id, trace.exported, trace.latency_ms),
    )


async def process_hermes(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        request = HermesRequest.model_validate(payload)
        try:
            value = INPUT_MODELS[request.action].model_validate(request.input)
        except ValidationError as exc:
            raise HermesFailure(
                400,
                "INVALID_REQUEST",
                "The action input did not match the Hermes contract.",
                details={"errors": exc.errors(include_url=False)},
            ) from exc
        fingerprint = _fingerprint(request)
        cached = await _existing_request(request, fingerprint)
        if cached:
            return cached, 200
        if request.action in {"status", "help"}:
            response = await _status_or_help(request)
        elif request.action == "onboard":
            response = await _onboard(request, value)  # type: ignore[arg-type]
        elif request.action in {"daily", "oracle"}:
            response = await _reading(request, value)  # type: ignore[arg-type]
        else:
            response = await _battle(request, value)  # type: ignore[arg-type]
        await _remember_request(request, fingerprint, response)
        return response, 200
    except ValidationError as exc:
        failure = HermesFailure(
            400,
            "INVALID_REQUEST",
            "The request did not match the Hermes contract.",
            details={"errors": exc.errors(include_url=False)},
        )
        return _error(payload, failure), failure.status
    except HermesFailure as failure:
        return _error(payload, failure), failure.status
    except Exception:
        failure = HermesFailure(
            502,
            "UPSTREAM_UNAVAILABLE",
            "The Kundli office could not complete that request. Please retry once.",
            retryable=True,
        )
        return _error(payload, failure), failure.status
