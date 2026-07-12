#!/usr/bin/env python3
"""Validate and call the public Kundli Kombat POST /hermes endpoint.

Request JSON is read from stdin so birth details are not written to a repo file.
This helper uses only the Python standard library and never talks to Telegram.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from typing import Any, NoReturn
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

API_BASE_URL = "https://meter-transit-laws-pine.trycloudflare.com"
CONTRACT_VERSION = "1"
ENTERTAINMENT_FOOTER = "for reflection and fun, not fate."
ACTIONS = {"status", "help", "onboard", "daily", "oracle", "celebrity_battle"}
CONTENT_ACTIONS = {"onboard", "daily", "oracle", "celebrity_battle"}
READING_TONES = {"comfort", "straight", "roast"}
BATTLE_TONES = {"friendly", "savage"}
LANGUAGES = {"en", "hinglish"}
SAFETY_POLICIES = {
    "death",
    "health",
    "pregnancy",
    "legal",
    "financial_doom",
    "abuse",
    "prompt_injection",
    "under13",
}


class ContractError(ValueError):
    """Raised when request or response JSON violates the repo contract."""


def fail(message: str, exit_code: int = 2) -> NoReturn:
    print(f"kundli-api: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path} must be an object")
    return value


def require_exact_keys(value: dict[str, Any], required: set[str], path: str) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise ContractError(f"{path} is missing: {', '.join(missing)}")
    if unknown:
        raise ContractError(f"{path} has unknown fields: {', '.join(unknown)}")


def require_string(value: Any, path: str, minimum: int = 1, maximum: int | None = None) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{path} must be a string")
    if len(value.strip()) < minimum:
        raise ContractError(f"{path} must contain at least {minimum} character(s)")
    if maximum is not None and len(value) > maximum:
        raise ContractError(f"{path} must contain at most {maximum} characters")
    return value


def require_choice(value: Any, choices: set[str], path: str) -> str:
    text = require_string(value, path)
    if text not in choices:
        raise ContractError(f"{path} must be one of: {', '.join(sorted(choices))}")
    return text


def require_uuid(value: Any, path: str) -> str:
    text = require_string(value, path)
    try:
        UUID(text)
    except ValueError as exc:
        raise ContractError(f"{path} must be a UUID") from exc
    return text


def validate_common_input(value: dict[str, Any], expected_keys: set[str], path: str = "input") -> None:
    require_exact_keys(value, expected_keys, path)
    if "language" in expected_keys:
        require_choice(value["language"], LANGUAGES, f"{path}.language")


def validate_request(document: Any) -> dict[str, Any]:
    request = require_object(document, "request")
    require_exact_keys(
        request,
        {"version", "requestId", "action", "identity", "playerId", "input"},
        "request",
    )
    if request["version"] != CONTRACT_VERSION:
        raise ContractError(f'request.version must be "{CONTRACT_VERSION}"')
    require_uuid(request["requestId"], "request.requestId")
    action = require_choice(request["action"], ACTIONS, "request.action")

    identity = require_object(request["identity"], "request.identity")
    require_exact_keys(identity, {"channel", "chatId", "userId", "threadId"}, "request.identity")
    if identity["channel"] != "telegram":
        raise ContractError('request.identity.channel must be "telegram"')
    require_string(identity["chatId"], "request.identity.chatId", maximum=100)
    require_string(identity["userId"], "request.identity.userId", maximum=100)
    if identity["threadId"] is not None:
        require_string(identity["threadId"], "request.identity.threadId", maximum=100)

    if request["playerId"] is not None:
        require_string(request["playerId"], "request.playerId", maximum=100)

    data = require_object(request["input"], "request.input")
    if action in {"status", "help"}:
        validate_common_input(data, set())
    elif action == "onboard":
        validate_common_input(
            data,
            {
                "name",
                "birthDate",
                "localBirthTime",
                "birthTimeUnknown",
                "birthPlace",
                "tone",
                "language",
            },
        )
        require_string(data["name"], "input.name", maximum=80)
        birth_date_text = require_string(data["birthDate"], "input.birthDate")
        try:
            birth_date = date.fromisoformat(birth_date_text)
        except ValueError as exc:
            raise ContractError("input.birthDate must be a real ISO YYYY-MM-DD date") from exc
        if birth_date > date.today():
            raise ContractError("input.birthDate must not be in the future")
        if not isinstance(data["birthTimeUnknown"], bool):
            raise ContractError("input.birthTimeUnknown must be a boolean")
        local_time = data["localBirthTime"]
        if data["birthTimeUnknown"]:
            if local_time is not None:
                raise ContractError("input.localBirthTime must be null when birthTimeUnknown is true")
        else:
            local_time = require_string(local_time, "input.localBirthTime")
            if len(local_time) != 5 or local_time[2] != ":":
                raise ContractError("input.localBirthTime must use HH:MM")
            try:
                hour, minute = (int(part) for part in local_time.split(":"))
            except ValueError as exc:
                raise ContractError("input.localBirthTime must use HH:MM") from exc
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ContractError("input.localBirthTime must be a real 24-hour local time")
        require_string(data["birthPlace"], "input.birthPlace", minimum=2, maximum=160)
        require_choice(data["tone"], READING_TONES, "input.tone")
    elif action == "daily":
        validate_common_input(data, {"tone", "language"})
        require_choice(data["tone"], READING_TONES, "input.tone")
    elif action == "oracle":
        validate_common_input(data, {"question", "tone", "language"})
        require_string(data["question"], "input.question", maximum=800)
        require_choice(data["tone"], READING_TONES, "input.tone")
    else:
        validate_common_input(data, {"celebrity", "tone", "language"})
        require_string(data["celebrity"], "input.celebrity", maximum=100)
        require_choice(data["tone"], BATTLE_TONES, "input.tone")

    return request


def validate_response(document: Any, request: dict[str, Any]) -> dict[str, Any]:
    response = require_object(document, "response")
    require_exact_keys(
        response,
        {"version", "requestId", "ok", "action", "playerId", "message", "data", "safety", "meta", "error"},
        "response",
    )
    for key in ("version", "requestId", "action"):
        if response[key] != request[key]:
            raise ContractError(f"response.{key} must echo request.{key}")
    if not isinstance(response["ok"], bool):
        raise ContractError("response.ok must be a boolean")
    if response["playerId"] is not None:
        require_string(response["playerId"], "response.playerId", maximum=100)
    message = require_string(response["message"], "response.message")
    require_object(response["data"], "response.data")

    safety = require_object(response["safety"], "response.safety")
    require_exact_keys(safety, {"refused", "policy"}, "response.safety")
    if not isinstance(safety["refused"], bool):
        raise ContractError("response.safety.refused must be a boolean")
    if safety["refused"]:
        require_choice(safety["policy"], SAFETY_POLICIES, "response.safety.policy")
    elif safety["policy"] is not None:
        raise ContractError("response.safety.policy must be null when refused is false")

    meta = require_object(response["meta"], "response.meta")
    require_exact_keys(meta, {"traceId", "traceExported", "latencyMs", "costUsd"}, "response.meta")
    require_string(meta["traceId"], "response.meta.traceId")
    if not isinstance(meta["traceExported"], bool):
        raise ContractError("response.meta.traceExported must be a boolean")
    if not isinstance(meta["latencyMs"], int) or isinstance(meta["latencyMs"], bool) or meta["latencyMs"] < 0:
        raise ContractError("response.meta.latencyMs must be a non-negative integer")
    if not isinstance(meta["costUsd"], (int, float)) or isinstance(meta["costUsd"], bool) or meta["costUsd"] < 0:
        raise ContractError("response.meta.costUsd must be a non-negative number")

    if response["ok"]:
        if response["error"] is not None:
            raise ContractError("response.error must be null when response.ok is true")
        if request["action"] in CONTENT_ACTIONS and not message.endswith(ENTERTAINMENT_FOOTER):
            raise ContractError(f'response.message must end with "{ENTERTAINMENT_FOOTER}"')
        if request["action"] in CONTENT_ACTIONS and not safety["refused"] and response["playerId"] is None:
            raise ContractError("successful content response must include response.playerId")
        if request["action"] in CONTENT_ACTIONS and not safety["refused"]:
            if not meta["traceExported"]:
                raise ContractError("LLM-backed content response must have response.meta.traceExported true")
            if meta["latencyMs"] >= 60_000:
                raise ContractError("content response exceeded the 60-second budget")
            if meta["costUsd"] >= 0.10:
                raise ContractError("content response reached or exceeded the $0.10 budget")

            data = response["data"]
            if request["action"] == "onboard" and request["input"]["birthTimeUnknown"]:
                if data.get("chartMode") != "solar":
                    raise ContractError('unknown-time onboarding must return data.chartMode "solar"')
                notice = data.get("timeNotice")
                if not isinstance(notice, str) or "approximate" not in notice.lower():
                    raise ContractError("unknown-time onboarding must return an approximate data.timeNotice")
            elif request["action"] in {"daily", "oracle"}:
                evidence = data.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    raise ContractError("non-refused reading must return non-empty data.evidence")
            elif request["action"] == "celebrity_battle":
                rounds = data.get("rounds")
                if not isinstance(rounds, list) or not rounds:
                    raise ContractError("celebrity battle must return non-empty data.rounds")
        elif safety["refused"] and response["data"].get("evidence") not in (None, []):
            raise ContractError("safety refusal must not return chart evidence")
    else:
        error = require_object(response["error"], "response.error")
        require_exact_keys(error, {"code", "message", "retryable", "details"}, "response.error")
        require_string(error["code"], "response.error.code")
        require_string(error["message"], "response.error.message")
        if not isinstance(error["retryable"], bool):
            raise ContractError("response.error.retryable must be a boolean")
        if error["details"] is not None:
            require_object(error["details"], "response.error.details")
    return response


def read_request() -> dict[str, Any]:
    try:
        document = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ContractError(f"stdin is not valid JSON: {exc}") from exc
    request = require_object(document, "request")
    request.setdefault("version", CONTRACT_VERSION)
    request.setdefault("requestId", str(uuid4()))
    request.setdefault("playerId", None)
    request.setdefault("input", {})
    return validate_request(request)


def call_api(request: dict[str, Any], timeout: float) -> tuple[int, Any]:
    body = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    http_request = Request(
        f"{API_BASE_URL}/hermes",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=timeout) as result:
            return result.status, json.load(result)
    except HTTPError as exc:
        try:
            return exc.code, json.load(exc)
        except json.JSONDecodeError as parse_error:
            raise ContractError(f"HTTP {exc.code} did not return contract JSON") from parse_error
    except URLError as exc:
        raise ContractError(f"could not reach Kundli API: {exc.reason}") from exc


def probe_health(timeout: float) -> None:
    try:
        with urlopen(f"{API_BASE_URL}/health", timeout=timeout) as result:
            document = json.load(result)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        fail(f"health probe failed: {exc}", 1)
    if result.status != 200 or document.get("ok") is not True:
        fail("health probe did not report ok=true", 1)
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))


def run_self_test() -> None:
    base = {
        "version": "1",
        "requestId": "8f97d87a-5ddb-49aa-8ab8-77fc82a4a669",
        "identity": {"channel": "telegram", "chatId": "123", "userId": "123", "threadId": None},
        "playerId": None,
    }
    fixtures = [
        {**base, "action": "status", "input": {}},
        {**base, "action": "help", "input": {}},
        {
            **base,
            "action": "onboard",
            "input": {
                "name": "Asha",
                "birthDate": "1995-08-17",
                "localBirthTime": None,
                "birthTimeUnknown": True,
                "birthPlace": "Pune, India",
                "tone": "straight",
                "language": "en",
            },
        },
        {**base, "action": "daily", "playerId": "player-1", "input": {"tone": "straight", "language": "en"}},
        {
            **base,
            "action": "oracle",
            "playerId": "player-1",
            "input": {"question": "What should I reflect on?", "tone": "comfort", "language": "en"},
        },
        {
            **base,
            "action": "celebrity_battle",
            "playerId": "player-1",
            "input": {"celebrity": "Virat Kohli", "tone": "friendly", "language": "en"},
        },
    ]
    for fixture in fixtures:
        validate_request(fixture)

    status_response = {
        "version": "1",
        "requestId": base["requestId"],
        "ok": True,
        "action": "status",
        "playerId": "player-1",
        "message": "Kundli Kombat is ready.",
        "data": {"service": "kundli-kombat-agency", "agencyReady": True, "hasPlayer": True, "capabilities": []},
        "safety": {"refused": False, "policy": None},
        "meta": {"traceId": "trace-status", "traceExported": True, "latencyMs": 1, "costUsd": 0},
        "error": None,
    }
    validate_response(status_response, fixtures[0])

    onboard_response = {
        "version": "1",
        "requestId": base["requestId"],
        "ok": True,
        "action": "onboard",
        "playerId": "player-1",
        "message": f"Your approximate solar chart is ready. {ENTERTAINMENT_FOOTER}",
        "data": {"chartMode": "solar", "timeNotice": "Birth time unknown; chart is approximate."},
        "safety": {"refused": False, "policy": None},
        "meta": {"traceId": "trace-onboard", "traceExported": True, "latencyMs": 25, "costUsd": 0.001},
        "error": None,
    }
    validate_response(onboard_response, fixtures[2])

    refusal_response = {
        **onboard_response,
        "playerId": None,
        "message": f"I can't provide an under-13 astrology reading. {ENTERTAINMENT_FOOTER}",
        "data": {},
        "safety": {"refused": True, "policy": "under13"},
    }
    validate_response(refusal_response, fixtures[2])
    print(f"validated {len(fixtures)} request fixtures and 3 response fixtures")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true", help="validate stdin request without network access")
    mode.add_argument("--probe", action="store_true", help="GET the public /health endpoint")
    mode.add_argument("--self-test", action="store_true", help="validate built-in fixtures without network access")
    parser.add_argument("--timeout", type=float, default=55.0, help="network timeout in seconds (default: 55)")
    args = parser.parse_args()
    if not 0 < args.timeout <= 55:
        fail("--timeout must be greater than 0 and no more than 55 seconds")
    if args.probe:
        probe_health(args.timeout)
        return
    if args.self_test:
        run_self_test()
        return
    try:
        request = read_request()
        if args.validate_only:
            print(json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True))
            return
        status, document = call_api(request, args.timeout)
        response = validate_response(document, request)
    except ContractError as exc:
        fail(str(exc), 1)
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    if not 200 <= status < 300 or not response["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
