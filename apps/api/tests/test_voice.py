from typing import Any

from fastapi.testclient import TestClient

from kundli_kombat.main import app


def test_voice_route_streams_mpeg_with_trace_headers(monkeypatch: Any) -> None:
    async def fake_voice(request: Any) -> tuple[bytes, str, bool]:
        assert request.kind == "daily"
        assert request.text == "Your chart has notes."
        return b"ID3-fake-mp3", "trace-voice", True

    monkeypatch.setattr("kundli_kombat.main.generate_voice", fake_voice)
    response = TestClient(app).post(
        "/voice", json={"text": "Your chart has notes.", "kind": "daily"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["x-langfuse-trace-id"] == "trace-voice"
    assert response.headers["x-voice-provider"] == "ElevenLabs"
    assert response.content == b"ID3-fake-mp3"


def test_voice_route_rejects_empty_text() -> None:
    response = TestClient(app).post("/voice", json={"text": "", "kind": "battle"})
    assert response.status_code == 422
