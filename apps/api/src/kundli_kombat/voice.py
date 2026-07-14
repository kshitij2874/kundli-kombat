from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .config import get_settings
from .observability import agent_step, traced_task


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    kind: Literal["daily", "battle", "oracle"]


class VoiceUnavailable(RuntimeError):
    pass


def _voice_settings(kind: Literal["daily", "battle", "oracle"]) -> dict[str, float | bool]:
    return {
        "stability": 0.48 if kind == "battle" else 0.62,
        "similarity_boost": 0.78,
        "style": 0.30 if kind == "battle" else 0.14,
        "speed": 0.88 if kind == "battle" else 0.92,
        "use_speaker_boost": True,
    }


def _voice_payload(request: VoiceRequest, model_id: str) -> dict[str, object]:
    return {
        "text": request.text.strip(),
        "model_id": model_id,
        "language_code": "en",
        "voice_settings": _voice_settings(request.kind),
    }


async def generate_voice(request: VoiceRequest) -> tuple[bytes, str, bool]:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise VoiceUnavailable("ElevenLabs is not configured")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.elevenlabs_api_key,
    }
    payload = _voice_payload(request, settings.elevenlabs_model_id)
    with traced_task("comms.tts", task=f"voice.{request.kind}") as trace:
        with agent_step(
            "comms.elevenlabs",
            {
                "provider": "elevenlabs",
                "model": settings.elevenlabs_model_id,
                "voiceId": settings.elevenlabs_voice_id,
                "characters": len(request.text),
            },
        ):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
                    response = await client.post(
                        url,
                        params={"output_format": "mp3_44100_128"},
                        headers=headers,
                        json=payload,
                    )
                response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                raise VoiceUnavailable("ElevenLabs could not generate this voice note") from exc
    return response.content, trace.trace_id, trace.exported
