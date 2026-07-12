from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .agency import create_reading
from .models import OnboardRequest, OnboardResponse, ReadingRequest, ReadingResponse
from .onboarding import onboard
from .observability import flush_traces, traced_task


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    flush_traces()


settings = get_settings()
app = FastAPI(title="Kundli Kombat Agency", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
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
            "convexConfigured": settings.convex_url is not None,
        }
    response["latencyMs"] = trace.latency_ms
    return response


@app.post("/onboard", response_model=OnboardResponse)
async def create_player(request: OnboardRequest) -> OnboardResponse:
    return await onboard(request)


@app.post("/reading", response_model=ReadingResponse)
async def reading(request: ReadingRequest) -> ReadingResponse:
    return await create_reading(request)


@app.post("/oracle", response_model=ReadingResponse)
async def oracle(request: ReadingRequest) -> ReadingResponse:
    request.kind = "oracle"
    return await create_reading(request)
