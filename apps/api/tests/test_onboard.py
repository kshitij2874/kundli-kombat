from fastapi.testclient import TestClient

from kundli_kombat.main import app


def test_onboard_returns_real_chart_with_evidence() -> None:
    response = TestClient(app).post(
        "/onboard",
        json={
            "name": "Anchor Test",
            "dob": "2000-01-01",
            "tob": "12:00",
            "tobUnknown": False,
            "place": "Greenwich",
            "lat": 51.4769,
            "lon": 0,
            "tz": "UTC",
            "tone": "straight",
            "lang": "en",
            "source": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["big3"]["sun"] == "Sagittarius"
    assert payload["evidence"]
    assert payload["chart"]["system"] == "sidereal"
    assert payload["chart"]["ayanamsa"] == "Lahiri"
    assert "Sagittarius" not in payload["identityLine"]
    assert "planet" not in payload["identityLine"].lower()
