from datetime import date, time

from kundli_kombat.battle_stats import fighter_stats
from kundli_kombat.ephemeris import calculate_chart
from kundli_kombat.main import app
from fastapi.testclient import TestClient


def _chart(dob: date) -> dict[str, object]:
    return calculate_chart(
        dob=dob,
        tob=time(12),
        tob_unknown=False,
        lat=28.6139,
        lon=77.2090,
        tz="Asia/Kolkata",
    )


def test_fighter_stats_are_deterministic_and_bounded() -> None:
    chart = _chart(date(1995, 4, 14))
    first = fighter_stats(chart)
    assert first == fighter_stats(chart)
    assert list(first) == ["Love", "Career", "Chaos"]
    assert all(0 <= value <= 100 for value in first.values())


def test_different_charts_create_different_fighters() -> None:
    assert fighter_stats(_chart(date(1995, 4, 14))) != fighter_stats(_chart(date(1989, 12, 13)))


def test_chart_preview_returns_ephemeral_known_person_fighter() -> None:
    response = TestClient(app).post(
        "/chart-preview",
        json={
            "name": "Partner",
            "dob": "1994-08-21",
            "tob": None,
            "tobUnknown": True,
            "place": "Pune, India",
            "lat": 18.5204,
            "lon": 73.8567,
            "tz": "Asia/Kolkata",
            "tone": "straight",
            "lang": "en",
            "source": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Partner"
    assert payload["chartMode"] == "solar"
    assert set(payload["stats"]) == {"Love", "Career", "Chaos"}
