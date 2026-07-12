from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .agency import create_reading
from .battles import battle, list_celebrities
from .battle_stats import fighter_stats
from .geocoding import search_places
from .hermes import process_hermes
from .models import (
    BattleRequest, BattleResponse, CelebritySummary, CelebrityVerifyRequest, ChartPreviewResponse,
    FighterStatsRequest, FighterStatsResponse,
    ConversationTurn, OnboardRequest, OnboardResponse, VerifiedCelebrity,
    PlaceSearchResponse, ReadingRequest, ReadingResponse,
)
from .onboarding import onboard
from .ephemeris import calculate_chart
from .observability import flush_traces, langfuse_authenticated, traced_task
from .voice import VoiceRequest, VoiceUnavailable, generate_voice
from .linkup import LinkupUnavailable, verify_celebrity
from .convex_client import ConvexUnavailable, query


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    flush_traces()


settings = get_settings()
app = FastAPI(title="Kundli Kombat Agency", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+)(:\d+)?|https://[a-z0-9-]+\.pages\.dev)$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.get("/health")
def health() -> dict[str, object]:
    with traced_task("manager.health", task="health") as trace:
        response = {
            "ok": True,
            "service": "kundli-kombat-agency",
            "version": app.version,
            "traceId": trace.trace_id,
            "traceExported": trace.exported,
            "agencyConfigured": settings.agency_configured,
            "langfuseAuthenticated": langfuse_authenticated(),
            "agencyReady": bool(settings.openai_api_key and langfuse_authenticated()),
            "convexConfigured": settings.convex_url is not None,
        }
    response["latencyMs"] = trace.latency_ms
    return response


@app.post("/hermes")
async def hermes_gateway(payload: dict[str, object]) -> JSONResponse:
    response, status = await process_hermes(payload)
    return JSONResponse(response, status_code=status)


@app.post("/voice")
async def voice(request: VoiceRequest) -> Response:
    try:
        audio, trace_id, exported = await generate_voice(request)
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Langfuse-Trace-Id": trace_id,
            "X-Trace-Exported": str(exported).lower(),
            "X-Voice-Provider": "ElevenLabs",
        },
    )


@app.post("/onboard", response_model=OnboardResponse)
async def create_player(request: OnboardRequest) -> OnboardResponse:
    return await onboard(request)


@app.post("/reading", response_model=ReadingResponse)
async def reading(request: ReadingRequest) -> ReadingResponse:
    return await create_reading(request)


@app.post("/oracle", response_model=ReadingResponse)
async def oracle(request: ReadingRequest) -> ReadingResponse:
    request.kind = "oracle"
    if not request.playerId.startswith("local-"):
        try:
            rows = await query("readings:recentOracle", {"playerId": request.playerId, "limit": 6})
            request.history = [
                ConversationTurn(question=str(row["question"]), answer=str(row["text"]))
                for row in rows if isinstance(row, dict) and row.get("question") and row.get("text")
            ]
        except ConvexUnavailable:
            request.history = []
    return await create_reading(request)


@app.get("/places", response_model=PlaceSearchResponse)
async def places(q: str) -> PlaceSearchResponse:
    return await search_places(q)


@app.get("/celebrities", response_model=list[CelebritySummary])
def celebrities() -> list[CelebritySummary]:
    return list_celebrities()


@app.post("/celebrities/verify", response_model=VerifiedCelebrity)
async def verify_new_celebrity(request: CelebrityVerifyRequest) -> VerifiedCelebrity:
    try:
        return VerifiedCelebrity.model_validate(await verify_celebrity(request.name))
    except LinkupUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/fighter-stats", response_model=FighterStatsResponse)
def calculate_fighter_stats(request: FighterStatsRequest) -> FighterStatsResponse:
    return FighterStatsResponse(stats=fighter_stats(request.chart))


@app.post("/chart-preview", response_model=ChartPreviewResponse)
def chart_preview(request: OnboardRequest) -> ChartPreviewResponse:
    """Calculate an ephemeral comparison chart without storing the person's birth data."""
    chart = calculate_chart(
        dob=request.dob, tob=request.tob, tob_unknown=request.tobUnknown,
        lat=request.lat, lon=request.lon, tz=request.tz,
    )
    return ChartPreviewResponse(
        name=request.name,
        chart=chart,
        stats=fighter_stats(chart),
        chartMode="solar" if request.tobUnknown else "birth-time",
        timeNotice=(
            "Birth time unknown: compatibility uses an approximate noon solar chart."
            if request.tobUnknown else None
        ),
    )


@app.post("/battle", response_model=BattleResponse)
async def create_battle(request: BattleRequest) -> BattleResponse:
    return await battle(request)
