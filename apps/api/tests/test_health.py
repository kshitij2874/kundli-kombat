from fastapi.testclient import TestClient

from kundli_kombat.main import app


def test_health_is_live_and_returns_trace_receipt() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "kundli-kombat-agency"
    assert payload["traceId"]
    assert payload["latencyMs"] >= 0

