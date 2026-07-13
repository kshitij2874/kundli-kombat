from dataclasses import dataclass


ELEMENT_BONUS = {"fire": 9, "earth": 6, "air": 7, "water": 8}
ELEMENTS = {
    "Aries": "fire",
    "Leo": "fire",
    "Sagittarius": "fire",
    "Taurus": "earth",
    "Virgo": "earth",
    "Capricorn": "earth",
    "Gemini": "air",
    "Libra": "air",
    "Aquarius": "air",
    "Cancer": "water",
    "Scorpio": "water",
    "Pisces": "water",
}


@dataclass(frozen=True)
class StatRule:
    planets: tuple[tuple[str, float], ...]
    element: str


STAT_RULES = {
    "Love": StatRule((("Venus", 0.60), ("Moon", 0.40)), "water"),
    "Career": StatRule((("Saturn", 0.40), ("Jupiter", 0.35), ("Sun", 0.25)), "earth"),
    "Chaos": StatRule((("Mars", 0.55), ("Uranus", 0.45)), "air"),
}


def _placements(chart: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = chart.get("placements", [])
    if not isinstance(raw, list):
        return {}
    return {
        str(item["planet"]): item
        for item in raw
        if isinstance(item, dict) and {"planet", "longitude", "sign"} <= item.keys()
    }


def fighter_stats(chart: dict[str, object]) -> dict[str, int]:
    """Derive stable 0–100 stats only from supplied planetary placements."""
    placements = _placements(chart)
    result: dict[str, int] = {}
    for stat, rule in STAT_RULES.items():
        score = 18.0
        for planet, weight in rule.planets:
            placement = placements.get(planet)
            if not placement:
                continue
            # Fold the zodiac longitude into a symmetric 0–73 contribution.
            longitude = float(placement["longitude"]) % 360
            signal = 73 - abs(180 - longitude) * (73 / 180)
            score += signal * weight
            element = ELEMENTS.get(str(placement["sign"]))
            if element == rule.element:
                score += ELEMENT_BONUS[element] * weight
        result[stat] = round(max(0, min(100, score)))
    return result
