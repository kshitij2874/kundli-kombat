from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Tone = Literal["comfort", "straight", "roast"]
Language = Literal["en", "hinglish"]
Source = Literal["web", "telegram"]


class OnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    dob: date
    tob: time | None = None
    tobUnknown: bool = False
    place: str = Field(min_length=2, max_length=160)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz: str = Field(min_length=1, max_length=80)
    tone: Tone = "straight"
    lang: Language = "en"
    source: Source = "web"

    @field_validator("tob")
    @classmethod
    def reject_seconds_precision(cls, value: time | None) -> time | None:
        if value and (value.second or value.microsecond):
            raise ValueError("Birth time must be entered to the minute")
        return value

    def model_post_init(self, __context: object) -> None:
        if not self.tobUnknown and self.tob is None:
            raise ValueError("tob is required unless tobUnknown is true")


class Evidence(BaseModel):
    planet: str
    sign: str
    longitude: float


class OnboardResponse(BaseModel):
    playerId: str
    chart: dict[str, object]
    big3: dict[str, str]
    nakshatra: str
    identityLine: str
    evidence: list[Evidence]
    chartMode: Literal["birth-time", "solar"]
    timeNotice: str | None
    traceId: str
    traceExported: bool
    latencyMs: int


ReadingKind = Literal["identity", "daily", "placement", "oracle", "deep"]


class ReadingRequest(BaseModel):
    playerId: str = Field(min_length=1, max_length=100)
    kind: ReadingKind
    chart: dict[str, object]
    question: str | None = Field(default=None, max_length=800)
    placement: str | None = Field(default=None, max_length=40)
    tone: Tone = "straight"
    lang: Language = "en"


class ReadingResponse(BaseModel):
    readingId: str
    kind: ReadingKind
    text: str
    evidence: list[Evidence]
    refused: bool
    policy: Literal["doom", "medical", "financial", "abuse", "under13"] | None
    plan: list[str]
    traceId: str
    traceExported: bool
    latencyMs: int
    costUsd: float

