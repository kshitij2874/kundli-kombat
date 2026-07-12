from dataclasses import dataclass

from .battle_stats import STAT_RULES, fighter_stats


ROUND_WEIGHTS = {"Love": 0.20, "Career": 0.20, "Luck": 0.20, "Fire": 0.20, "Chaos": 0.20}
ASPECTS = {
    "conjunction": (0, 14),
    "sextile": (60, 9),
    "square": (90, -12),
    "trine": (120, 12),
    "opposition": (180, -13),
}
PAIR_WEIGHTS = {
    "Communication": {
        ("Mercury", "Mercury"): 1.4, ("Mercury", "Moon"): 1.2,
        ("Moon", "Mercury"): 1.2, ("Moon", "Moon"): 1.0,
    },
    "Chaos": {
        ("Mars", "Mars"): 1.2, ("Mars", "Uranus"): 1.4, ("Uranus", "Mars"): 1.4,
        ("Sun", "Mars"): 1.0, ("Mars", "Sun"): 1.0,
        ("Sun", "Uranus"): 1.1, ("Uranus", "Sun"): 1.1,
    },
    "Loyalty": {
        ("Venus", "Saturn"): 1.4, ("Saturn", "Venus"): 1.4,
        ("Venus", "Moon"): 1.1, ("Moon", "Venus"): 1.1,
        ("Saturn", "Moon"): 1.0, ("Moon", "Saturn"): 1.0,
    },
}
ELEMENTS = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}


@dataclass(frozen=True)
class AspectHit:
    p1_planet: str
    p2_planet: str
    aspect: str
    orb: float
    weighted_value: float

    @property
    def label(self) -> str:
        return f"{self.p1_planet}–{self.p2_planet} {self.aspect} ({self.orb:.1f}° orb)"


@dataclass(frozen=True)
class ScoredRound:
    name: str
    p1_score: int
    p2_score: int
    compatibility_score: int
    aspects: tuple[str, ...]


def _angle(a: float, b: float) -> float:
    difference = abs((a - b) % 360)
    return min(difference, 360 - difference)


def _aspect(angle: float) -> tuple[str, float, int] | None:
    candidates = [
        (name, abs(angle - target), value)
        for name, (target, value) in ASPECTS.items()
        if abs(angle - target) <= 6
    ]
    return min(candidates, key=lambda item: item[1]) if candidates else None


def _placement_map(chart: dict[str, object]) -> dict[str, dict[str, object]]:
    placements = chart.get("placements", [])
    if not isinstance(placements, list):
        return {}
    return {
        str(item["planet"]): item for item in placements
        if isinstance(item, dict) and {"planet", "longitude"} <= item.keys()
    }


def _round(name: str, p1: dict[str, dict[str, object]], p2: dict[str, dict[str, object]]) -> ScoredRound:
    hits: list[AspectHit] = []
    for pair, pair_weight in PAIR_WEIGHTS[name].items():
        if pair[0] not in p1 or pair[1] not in p2:
            continue
        result = _aspect(_angle(float(p1[pair[0]]["longitude"]), float(p2[pair[1]]["longitude"])))
        if result:
            aspect_name, orb, value = result
            closeness = 1 - orb / 6
            hits.append(AspectHit(pair[0], pair[1], aspect_name, orb, value * pair_weight * (0.65 + 0.35 * closeness)))

    total = sum(hit.weighted_value for hit in hits)
    compatibility = round(max(0, min(100, 55 + total)))
    if name == "Chaos":
        sun1, sun2 = p1.get("Sun"), p2.get("Sun")
        if sun1 and sun2 and ELEMENTS.get(str(sun1.get("sign"))) != ELEMENTS.get(str(sun2.get("sign"))):
            compatibility = max(0, compatibility - 7)

    # The edge uses only chart facts: the relevant planets' absolute speeds.
    speed1 = sum(abs(float(p1[planet].get("speed", 0))) for planet, _ in PAIR_WEIGHTS[name] if planet in p1)
    speed2 = sum(abs(float(p2[planet].get("speed", 0))) for _, planet in PAIR_WEIGHTS[name] if planet in p2)
    edge = max(-8, min(8, round((speed1 - speed2) * 0.8)))
    p1_score = max(0, min(100, compatibility + edge))
    p2_score = max(0, min(100, compatibility - edge))
    labels = tuple(hit.label for hit in sorted(hits, key=lambda item: abs(item.weighted_value), reverse=True)[:3])
    return ScoredRound(name, p1_score, p2_score, compatibility, labels)


def score_battle(p1_chart: dict[str, object], p2_chart: dict[str, object]) -> tuple[list[ScoredRound], int, str]:
    p1_stats, p2_stats = fighter_stats(p1_chart), fighter_stats(p2_chart)
    p1_placements, p2_placements = _placement_map(p1_chart), _placement_map(p2_chart)
    rounds = []
    for name, rule in STAT_RULES.items():
        p1_score, p2_score = p1_stats[name], p2_stats[name]
        planets = [planet for planet, _ in rule.planets]
        evidence = tuple(
            f"{planet}: {p1_placements[planet].get('sign', '?')} vs {p2_placements[planet].get('sign', '?')}"
            for planet in planets
            if planet in p1_placements and planet in p2_placements
        )
        rounds.append(ScoredRound(
            name=name,
            p1_score=p1_score,
            p2_score=p2_score,
            compatibility_score=100 - abs(p1_score - p2_score),
            aspects=evidence,
        ))
    verdict = round(sum(item.compatibility_score * ROUND_WEIGHTS[item.name] for item in rounds))
    p1_wins = sum(item.p1_score > item.p2_score for item in rounds)
    p2_wins = sum(item.p2_score > item.p1_score for item in rounds)
    winner = "tie" if p1_wins == p2_wins else "p1" if p1_wins > p2_wins else "p2"
    return rounds, verdict, winner
