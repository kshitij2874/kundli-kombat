from uuid import uuid4

from .convex_client import ConvexUnavailable, mutation
from .ephemeris import calculate_chart
from .models import Evidence, OnboardRequest, OnboardResponse
from .observability import traced_task


def _identity_line(big3: dict[str, str]) -> str:
    drives = {
        "Aries": "You like to start fast and learn by doing",
        "Taurus": "You build slowly, steadily, and with care",
        "Gemini": "You stay curious and think in many directions",
        "Cancer": "You protect what matters and notice how people feel",
        "Leo": "You bring warmth, courage, and a wish to be seen",
        "Virgo": "You notice small details and enjoy making things better",
        "Libra": "You look for fairness and help people meet in the middle",
        "Scorpio": "You feel things deeply and do not give up easily",
        "Sagittarius": "You chase new ideas, freedom, and bigger adventures",
        "Capricorn": "You set serious goals and keep climbing toward them",
        "Aquarius": "You think differently and care about improving the group",
        "Pisces": "You lead with imagination, kindness, and strong intuition",
    }
    feelings = {
        "Aries": "Your feelings arrive quickly and honestly",
        "Taurus": "You feel safest with calm, comfort, and steady people",
        "Gemini": "Talking and learning help you understand your feelings",
        "Cancer": "You care deeply and remember how people make you feel",
        "Leo": "You need warmth, loyalty, and room to express your heart",
        "Virgo": "You handle feelings by fixing problems and helping",
        "Libra": "Peace and fair treatment help you feel balanced",
        "Scorpio": "Your feelings run deep, even when you keep them private",
        "Sagittarius": "Space, honesty, and hope help you reset",
        "Capricorn": "You often stay composed and show care through actions",
        "Aquarius": "You need breathing room before feelings make sense",
        "Pisces": "You easily pick up moods and need quiet time to recharge",
    }
    drive = drives.get(big3["sun"], "You have your own way of moving through the world")
    feeling = feelings.get(big3["moon"], "Your feelings have their own clear rhythm")
    if big3["rising"] == "Solar chart":
        return f"Dekho, {drive[0].lower()}{drive[1:]}. {feeling}. Your birth time is unknown, so we leave first impressions out instead of guessing."
    return f"Dekho, {drive[0].lower()}{drive[1:]}. {feeling}. Together, that is the energy people meet when you walk into a room."


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
        if request.tob:
            player_args["tob"] = request.tob.isoformat(timespec="minutes")
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
                if request.tobUnknown
                else None
            ),
            traceId=trace.trace_id,
            traceExported=trace.exported,
            latencyMs=0,
        )
    response.latencyMs = trace.latency_ms
    return response
