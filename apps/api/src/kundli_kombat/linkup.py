import json
from datetime import date

import httpx
from pydantic import BaseModel

from .battle_stats import fighter_stats
from .config import get_settings
from .convex_client import ConvexUnavailable, mutation
from .ephemeris import calculate_chart
from .geocoding import search_places
from .observability import agent_step, traced_task


class LinkupUnavailable(RuntimeError):
    pass


class BirthRecord(BaseModel):
    name: str
    birthDate: date
    birthCity: str
    birthCountry: str


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "birthDate": {"type": "string", "description": "YYYY-MM-DD"},
        "birthCity": {"type": "string", "description": "Current unambiguous city name"},
        "birthCountry": {"type": "string", "description": "Current country name"},
    },
    "required": ["name", "birthDate", "birthCity", "birthCountry"],
    "additionalProperties": False,
}


async def verify_celebrity(name: str) -> dict[str, object]:
    settings = get_settings()
    if not settings.linkup_api_key:
        raise LinkupUnavailable("Linkup is not configured")
    with traced_task("research.linkup", task="celebrity.verify"):
        with agent_step("research.linkup", {"provider": "linkup", "depth": "standard"}):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
                    response = await client.post(
                        "https://api.linkup.so/v1/search",
                        headers={"Authorization": f"Bearer {settings.linkup_api_key}"},
                        json={
                            "q": (
                                f"Find the verified birth date and birthplace for celebrity {name}. "
                                "Return date as YYYY-MM-DD and return the birthplace as separate modern, "
                                "unambiguous birthCity and birthCountry fields (not a historical region). "
                                "Use a reputable biographical source."
                            ),
                            "depth": "standard",
                            "outputType": "structured",
                            "structuredOutputSchema": json.dumps(SCHEMA),
                            "includeSources": True,
                        },
                    )
                response.raise_for_status()
                payload = response.json()
                record = BirthRecord.model_validate(payload["data"])
                sources = payload.get("sources") or []
                source_url = str(sources[0]["url"])
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                raise LinkupUnavailable("Linkup could not verify that celebrity") from exc
        places = await search_places(f"{record.birthCity}, {record.birthCountry}")
        if not places.results:
            raise LinkupUnavailable("The verified birthplace could not be resolved")
        place = places.results[0]
        chart = calculate_chart(
            dob=record.birthDate, tob=None, tob_unknown=True,
            lat=place.lat, lon=place.lon, tz=place.timezone,
        )
        result = {
            "name": record.name,
            "dob": record.birthDate.isoformat(),
            "place": place.label,
            "sourceUrl": source_url,
            "chart": chart,
            "big3": chart["big3"],
            "stats": fighter_stats(chart),
            "timeApproximate": True,
            "verifiedBy": "Linkup",
        }
        try:
            await mutation("celebrities:upsert", {
                "name": result["name"], "dob": result["dob"], "tobUnknown": True,
                "place": result["place"], "sourceUrl": source_url,
                "chart": chart, "big3": chart["big3"],
            })
        except ConvexUnavailable:
            pass
        return result
