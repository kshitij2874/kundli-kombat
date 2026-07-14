from typing import Any

from fastapi.testclient import TestClient

from kundli_kombat.main import app
from kundli_kombat.voice import VoiceRequest, _voice_payload, _voice_settings


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


def test_voice_speed_is_readable_and_battle_is_slowest() -> None:
    battle = _voice_settings("battle")
    daily = _voice_settings("daily")

    assert battle["speed"] == 0.88
    assert daily["speed"] == 0.92
    assert 0.7 <= float(battle["speed"]) < float(daily["speed"]) < 1.0


def test_voice_payload_pins_english_for_indian_english_delivery() -> None:
    request = VoiceRequest(text="  Your stars are ready.  ", kind="oracle")

    payload = _voice_payload(request, "eleven_flash_v2_5")

    assert payload["text"] == "Your stars are ready."
    assert payload["model_id"] == "eleven_flash_v2_5"
    assert payload["language_code"] == "en"
    assert payload["voice_settings"] == _voice_settings("oracle")
