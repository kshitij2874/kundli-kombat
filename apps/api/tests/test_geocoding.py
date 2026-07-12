from datetime import date, time

from kundli_kombat.ephemeris import calculate_chart
from kundli_kombat.geocoding import (
    nearest_big_city_suggestions,
    normalize_place_query,
    provider_place_query,
)


def test_common_indian_city_alias_is_normalized() -> None:
    assert normalize_place_query("  BANGALORE!!!  ") == "bengaluru"
    assert normalize_place_query("Bombay, Maharashtra") == "mumbai maharashtra"


def test_typo_gets_big_city_suggestion_instead_of_dead_end() -> None:
    suggestions = nearest_big_city_suggestions("Banglore")
    assert suggestions
    assert suggestions[0] == "Bengaluru, India"


def test_provider_query_strips_country_suffix() -> None:
    assert provider_place_query("London, United Kingdom") == "london"


def test_historical_timezone_rules_drive_utc_conversion() -> None:
    winter = calculate_chart(
        dob=date(1980, 1, 15), tob=time(12), tob_unknown=False,
        lat=40.7128, lon=-74.0060, tz="America/New_York",
    )
    summer = calculate_chart(
        dob=date(1980, 7, 15), tob=time(12), tob_unknown=False,
        lat=40.7128, lon=-74.0060, tz="America/New_York",
    )
    assert winter["utcTimestamp"].endswith("17:00:00+00:00")
    assert summer["utcTimestamp"].endswith("16:00:00+00:00")
