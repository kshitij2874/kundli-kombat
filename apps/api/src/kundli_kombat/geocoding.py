import re
import unicodedata
from time import time

import httpx
from rapidfuzz import fuzz, process

from .convex_client import ConvexUnavailable, mutation, query
from .models import PlaceResult, PlaceSearchResponse
from .observability import agent_step


OPEN_METEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
BIG_CITIES = (
    "Bengaluru, India", "Mumbai, India", "Delhi, India", "Kolkata, India",
    "Chennai, India", "Hyderabad, India", "Pune, India", "Ahmedabad, India",
    "Jaipur, India", "Lucknow, India", "Ranchi, India", "Chandigarh, India",
    "London, United Kingdom", "New York, United States", "Dubai, United Arab Emirates",
    "Singapore", "Sydney, Australia", "Toronto, Canada", "Copenhagen, Denmark",
)
ALIASES = {
    "bangalore": "bengaluru",
    "bangaluru": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "madras": "chennai",
    "gurgaon": "gurugram",
}
CITY_SEARCH_NAMES = {normalize: city for city in BIG_CITIES for normalize in (city.split(",", 1)[0].lower(),)}
CITY_SEARCH_NAMES.update({alias: "Bengaluru, India" for alias in ("bangalore", "bangaluru", "banglore")})
CITY_SEARCH_NAMES.update({"bombay": "Mumbai, India", "calcutta": "Kolkata, India", "madras": "Chennai, India"})
_LOCAL_CACHE: dict[str, tuple[float, list[dict[str, object]]]] = {}


def normalize_place_query(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()
    tokens = [ALIASES.get(token, token) for token in cleaned.split()]
    return " ".join(tokens)


def nearest_big_city_suggestions(value: str, limit: int = 3) -> list[str]:
    query_value = normalize_place_query(value)
    matches = process.extract(query_value, CITY_SEARCH_NAMES.keys(), scorer=fuzz.WRatio, limit=limit * 2)
    suggestions: list[str] = []
    for search_name, score, _ in matches:
        city = CITY_SEARCH_NAMES[search_name]
        if score >= 35 and city not in suggestions:
            suggestions.append(city)
        if len(suggestions) == limit:
            break
    return suggestions


async def _cached(key: str) -> list[dict[str, object]] | None:
    local = _LOCAL_CACHE.get(key)
    if local and time() - local[0] < CACHE_TTL_SECONDS:
        return local[1]
    try:
        record = await query("places:get", {"key": key})
    except ConvexUnavailable:
        return None
    if not record or time() * 1000 - float(record["createdAt"]) > CACHE_TTL_SECONDS * 1000:
        return None
    results = record["results"]
    if isinstance(results, list):
        _LOCAL_CACHE[key] = (time(), results)
        return results
    return None


async def _save_cache(key: str, original: str, results: list[dict[str, object]]) -> None:
    _LOCAL_CACHE[key] = (time(), results)
    if len(_LOCAL_CACHE) > 256:
        oldest = min(_LOCAL_CACHE, key=lambda item: _LOCAL_CACHE[item][0])
        _LOCAL_CACHE.pop(oldest, None)
    try:
        await mutation("places:put", {"key": key, "query": original, "results": results})
    except ConvexUnavailable:
        return


def _parse_result(item: dict[str, object]) -> PlaceResult | None:
    timezone = item.get("timezone")
    latitude = item.get("latitude")
    longitude = item.get("longitude")
    if not isinstance(timezone, str) or latitude is None or longitude is None:
        return None
    name = str(item.get("name", ""))
    country = str(item.get("country", ""))
    admin1 = str(item["admin1"]) if item.get("admin1") else None
    label_parts = [name, admin1, country]
    label = ", ".join(dict.fromkeys(part for part in label_parts if part))
    return PlaceResult(
        id=f"{item.get('id', name)}:{timezone}", label=label, name=name, country=country,
        admin1=admin1, lat=float(latitude), lon=float(longitude), timezone=timezone,
    )


async def search_places(value: str) -> PlaceSearchResponse:
    original = value.strip()
    key = normalize_place_query(original)
    if len(key) < 2:
        return PlaceSearchResponse(query=original, results=[], suggestions=[], cached=False)
    cached = await _cached(key)
    if cached is not None:
        return PlaceSearchResponse(
            query=original,
            results=[PlaceResult.model_validate(item) for item in cached],
            suggestions=[],
            cached=True,
        )
    with agent_step("geocoder.search", {"provider": "open-meteo", "queryKey": key}):
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(OPEN_METEO_URL, params={
                "name": key, "count": 5, "language": "en", "format": "json",
            })
            response.raise_for_status()
            raw = response.json().get("results", [])
    results = [parsed for item in raw if isinstance(item, dict) and (parsed := _parse_result(item))]
    serialized = [result.model_dump() for result in results]
    await _save_cache(key, original, serialized)
    suggestions = [] if results else nearest_big_city_suggestions(original)
    return PlaceSearchResponse(
        query=original, results=results, suggestions=suggestions, cached=False,
    )
