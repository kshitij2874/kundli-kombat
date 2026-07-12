from typing import Any

from fastapi.testclient import TestClient

from kundli_kombat.main import app
from kundli_kombat.models import Evidence, OnboardResponse, ReadingResponse


BASE_REQUEST = {
    "version": "1",
    "requestId": "8f97d87a-5ddb-49aa-8ab8-77fc82a4a669",
    "identity": {
        "channel": "telegram",
        "chatId": "123",
        "userId": "123",
        "threadId": None,
    },
    "playerId": None,
}


async def _no_record_query(path: str, args: dict[str, Any]) -> None:
    return None


async def _mutation(path: str, args: dict[str, Any]) -> str:
    return "stored"


def test_hermes_status_is_contract_shaped(monkeypatch: Any) -> None:
    monkeypatch.setattr("kundli_kombat.hermes.query", _no_record_query)
    monkeypatch.setattr("kundli_kombat.hermes.mutation", _mutation)
    response = TestClient(app).post(
        "/hermes", json={**BASE_REQUEST, "action": "status", "input": {}}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["action"] == "status"
    assert payload["data"]["hasPlayer"] is False
    assert payload["meta"]["traceId"]


def test_hermes_unknown_time_onboarding_is_explicitly_approximate(monkeypatch: Any) -> None:
    from kundli_kombat.models import PlaceResult, PlaceSearchResponse

    async def fake_places(value: str) -> PlaceSearchResponse:
        return PlaceSearchResponse(
            query=value,
            results=[PlaceResult(
                id="pune:Asia/Kolkata", label="Pune, India", name="Pune",
                country="India", lat=18.5204, lon=73.8567, timezone="Asia/Kolkata",
            )],
            suggestions=[],
            cached=True,
        )

    async def fake_onboard(request: Any) -> OnboardResponse:
        assert request.source == "telegram"
        assert request.tobUnknown is True
        return OnboardResponse(
            playerId="player-telegram",
            chart={"placements": []},
            big3={"sun": "Leo", "moon": "Taurus", "rising": "Solar chart"},
            nakshatra="Rohini",
            identityLine="Leo drive, Taurus instincts.",
            evidence=[Evidence(planet="Sun", sign="Leo", longitude=130)],
            chartMode="solar",
            timeNotice="unknown",
            traceId="trace-onboard",
            traceExported=True,
            latencyMs=12,
        )

    monkeypatch.setattr("kundli_kombat.hermes.query", _no_record_query)
    monkeypatch.setattr("kundli_kombat.hermes.mutation", _mutation)
    monkeypatch.setattr("kundli_kombat.hermes.search_places", fake_places)
    monkeypatch.setattr("kundli_kombat.hermes.onboard", fake_onboard)
    request = {
        **BASE_REQUEST,
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
    }
    response = TestClient(app).post("/hermes", json=request)
    assert response.status_code == 200
    payload = response.json()
    assert payload["playerId"] == "player-telegram"
    assert "approximate" in payload["data"]["timeNotice"]
    assert payload["message"].endswith("for reflection and fun, not fate.")


def test_hermes_oracle_maps_safety_policy(monkeypatch: Any) -> None:
    async def identity_query(path: str, args: dict[str, Any]) -> Any:
        if path == "hermes:getRequest":
            return None
        return {
            "playerId": "player-telegram",
            "player": {"chart": {"placements": []}},
        }

    async def fake_reading(request: Any) -> ReadingResponse:
        return ReadingResponse(
            readingId="reading-1",
            kind="oracle",
            text="I can’t predict death or frightening outcomes. for reflection and fun, not fate.",
            evidence=[],
            refused=True,
            policy="doom",
            plan=["Safety screen", "Warm refusal"],
            traceId="trace-refusal",
            traceExported=True,
            latencyMs=3,
            costUsd=0,
        )

    monkeypatch.setattr("kundli_kombat.hermes.query", identity_query)
    monkeypatch.setattr("kundli_kombat.hermes.mutation", _mutation)
    monkeypatch.setattr("kundli_kombat.hermes.create_reading", fake_reading)
    request = {
        **BASE_REQUEST,
        "playerId": "player-telegram",
        "action": "oracle",
        "input": {
            "question": "When will I die?",
            "tone": "straight",
            "language": "en",
        },
    }
    response = TestClient(app).post("/hermes", json=request)
    assert response.status_code == 200
    payload = response.json()
    assert payload["safety"] == {"refused": True, "policy": "death"}
    assert payload["data"]["evidence"] == []
