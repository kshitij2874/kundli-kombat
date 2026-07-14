from fastapi.testclient import TestClient

from kundli_kombat.main import app, settings


def test_health_is_live_and_returns_trace_receipt() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "kundli-kombat-agency"
    assert payload["traceId"]
    assert payload["latencyMs"] >= 0


def test_deployed_origin_requires_gateway_secret_except_for_health() -> None:
    previous = settings.origin_shared_secret
    settings.origin_shared_secret = "test-origin-secret"
    try:
        client = TestClient(app)
        assert client.get("/health").status_code == 200
        assert client.get("/celebrities").status_code == 401
        response = client.get(
            "/celebrities",
            headers={"X-KK-Origin-Secret": "test-origin-secret"},
        )
        assert response.status_code == 200
    finally:
        settings.origin_shared_secret = previous
