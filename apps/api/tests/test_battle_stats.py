from datetime import date, time

from kundli_kombat.battle_stats import fighter_stats
from kundli_kombat.ephemeris import calculate_chart


def _chart(dob: date) -> dict[str, object]:
    return calculate_chart(
        dob=dob, tob=time(12), tob_unknown=False,
        lat=28.6139, lon=77.2090, tz="Asia/Kolkata",
    )


def test_fighter_stats_are_deterministic_and_bounded() -> None:
    chart = _chart(date(1995, 4, 14))
    first = fighter_stats(chart)
    assert first == fighter_stats(chart)
    assert list(first) == ["Love", "Career", "Luck", "Fire", "Chaos"]
    assert all(0 <= value <= 100 for value in first.values())


def test_different_charts_create_different_fighters() -> None:
    assert fighter_stats(_chart(date(1995, 4, 14))) != fighter_stats(_chart(date(1989, 12, 13)))
