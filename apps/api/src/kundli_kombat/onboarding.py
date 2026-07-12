from uuid import uuid4

from .convex_client import ConvexUnavailable, mutation
from .ephemeris import calculate_chart
from .models import Evidence, OnboardRequest, OnboardResponse
from .observability import traced_task


def _identity_line(big3: dict[str, str]) -> str:
    if big3["rising"] == "Solar chart":
        return f"{big3['sun']} drive, {big3['moon']} instincts — your birth time is unknown, so the rising sign stays off the scoreboard."
    return f"{big3['sun']} drive, {big3['moon']} instincts, {big3['rising']} entrance — calm face, cosmic plot twist."


async def onboard(request: OnboardRequest) -> OnboardResponse:
    with traced_task("manager.onboard", task="onboard") as trace:
        chart = calculate_chart(
            dob=request.dob,
            tob=request.tob,
            tob_unknown=request.tobUnknown,
            lat=request.lat,
            lon=request.lon,
            tz=request.tz,
        )
        big3 = chart["big3"]
        if not isinstance(big3, dict):
            raise TypeError("Chart big3 must be an object")
        placements = chart["placements"]
        if not isinstance(placements, list):
            raise TypeError("Chart placements must be a list")
        evidence = [
            Evidence(
                planet=str(item["planet"]),
                sign=str(item["sign"]),
                longitude=float(item["longitude"]),
            )
            for item in placements
            if item["planet"] in {"Sun", "Moon"}
        ]
        player_args = {
            "name": request.name,
            "dob": request.dob.isoformat(),
            "tob": request.tob.isoformat(timespec="minutes") if request.tob else None,
            "tobUnknown": request.tobUnknown,
            "place": request.place,
            "lat": request.lat,
            "lon": request.lon,
            "tz": request.tz,
            "chart": chart,
            "big3": big3,
            "nakshatra": chart["nakshatra"],
            "tone": request.tone,
            "lang": request.lang,
            "source": request.source,
        }
        try:
            player_id = str(await mutation("players:create", player_args))
        except ConvexUnavailable:
            player_id = f"local-{uuid4().hex}"
        response = OnboardResponse(
            playerId=player_id,
            chart=chart,
            big3={key: str(value) for key, value in big3.items()},
            nakshatra=str(chart["nakshatra"]),
            identityLine=_identity_line({key: str(value) for key, value in big3.items()}),
            evidence=evidence,
            chartMode="solar" if request.tobUnknown else "birth-time",
            timeNotice=(
                "Birth time unknown: this is an honest noon solar chart. Rising sign and houses are not claimed."
                if request.tobUnknown else None
            ),
            traceId=trace.trace_id,
            traceExported=trace.exported,
            latencyMs=0,
        )
    response.latencyMs = trace.latency_ms
    return response

