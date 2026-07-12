from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from threading import RLock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe


SIGNS = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)
PLANETS = (
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN), ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE),
    ("Pluto", swe.PLUTO), ("North Node", swe.TRUE_NODE),
)
_LOCK = RLock()


@dataclass(frozen=True)
class EphemerisAnchor:
    julian_day: float
    tropical_sun_longitude: float
    lahiri_ayanamsa: float
    sidereal_sun_longitude: float


def _sign(longitude: float) -> tuple[str, float]:
    normalized = longitude % 360
    index = int(normalized // 30)
    return SIGNS[index], normalized % 30


def _julian_day(dob: date, tob: time, timezone_name: str) -> tuple[float, str]:
    try:
        local = datetime.combine(dob, tob, tzinfo=ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_name}") from exc
    utc = local.astimezone(UTC)
    decimal_hour = utc.hour + utc.minute / 60 + utc.second / 3600
    return swe.julday(utc.year, utc.month, utc.day, decimal_hour, swe.GREG_CAL), utc.isoformat()


def verify_anchor() -> EphemerisAnchor:
    jd = swe.julday(2000, 1, 1, 12.0, swe.GREG_CAL)
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        tropical = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][0] % 360
        ayanamsa = swe.get_ayanamsa_ut(jd)
        sidereal = swe.calc_ut(
            jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL,
        )[0][0] % 360
    return EphemerisAnchor(jd, tropical, ayanamsa, sidereal)


def calculate_chart(
    *, dob: date, tob: time | None, tob_unknown: bool, lat: float, lon: float, tz: str,
) -> dict[str, object]:
    effective_time = time(12, 0) if tob_unknown else tob
    if effective_time is None:
        raise ValueError("Birth time is required for a birth-time chart")
    jd, utc_timestamp = _julian_day(dob, effective_time, tz)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    placements: list[dict[str, object]] = []
    with _LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        ayanamsa = swe.get_ayanamsa_ut(jd)
        for name, body in PLANETS:
            values, _ = swe.calc_ut(jd, body, flags)
            longitude = values[0] % 360
            sign, degree = _sign(longitude)
            placements.append({
                "planet": name,
                "longitude": round(longitude, 6),
                "sign": sign,
                "degree": round(degree, 4),
                "speed": round(values[3], 6),
                "retrograde": values[3] < 0,
            })
        if tob_unknown:
            ascendant = None
            houses = None
        else:
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
            ascendant = ascmc[0] % 360
            houses = [round(cusp % 360, 6) for cusp in cusps]

    by_name = {placement["planet"]: placement for placement in placements}
    moon_longitude = float(by_name["Moon"]["longitude"])
    span = 360 / 27
    nakshatra_index = int(moon_longitude // span)
    pada = int((moon_longitude % span) // (span / 4)) + 1
    if ascendant is None:
        rising = "Solar chart"
    else:
        rising = _sign(ascendant)[0]
    big3 = {
        "sun": str(by_name["Sun"]["sign"]),
        "moon": str(by_name["Moon"]["sign"]),
        "rising": rising,
    }
    return {
        "system": "sidereal",
        "ayanamsa": "Lahiri",
        "ayanamsaDegrees": round(ayanamsa, 6),
        "julianDayUt": round(jd, 8),
        "utcTimestamp": utc_timestamp,
        "chartMode": "solar" if tob_unknown else "birth-time",
        "timeApproximate": tob_unknown,
        "placements": placements,
        "ascendantLongitude": round(ascendant, 6) if ascendant is not None else None,
        "houses": houses,
        "big3": big3,
        "nakshatra": NAKSHATRAS[nakshatra_index],
        "nakshatraPada": pada,
    }

