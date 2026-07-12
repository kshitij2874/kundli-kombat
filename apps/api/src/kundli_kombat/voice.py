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
    payload = {
        "text": request.text.strip(),
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {
            "stability": 0.42 if request.kind == "battle" else 0.58,
            "similarity_boost": 0.78,
            "style": 0.38 if request.kind == "battle" else 0.18,
            "use_speaker_boost": True,
        },
    }
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
