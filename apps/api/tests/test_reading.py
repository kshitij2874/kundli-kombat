from fastapi.testclient import TestClient

from kundli_kombat.ephemeris import calculate_chart
from kundli_kombat.main import app


def _chart() -> dict[str, object]:
    from datetime import date, time
    return calculate_chart(
        dob=date(2000, 1, 1), tob=time(12), tob_unknown=False,
        lat=51.4769, lon=0, tz="UTC",
    )


def test_reading_has_evidence_footer_and_plan() -> None:
    response = TestClient(app).post("/reading", json={
        "playerId": "local-test", "kind": "daily", "chart": _chart(),
        "tone": "roast", "lang": "en",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["evidence"]
    assert payload["text"].lower().endswith("for reflection and fun, not fate.")
    assert len(payload["plan"]) >= 2


def test_doom_question_is_refused_without_chart_claims() -> None:
    response = TestClient(app).post("/oracle", json={
        "playerId": "local-test", "kind": "oracle", "chart": _chart(),
        "question": "When will I die?", "tone": "straight", "lang": "en",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["policy"] == "doom"
    assert payload["costUsd"] == 0

