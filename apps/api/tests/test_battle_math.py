from datetime import date, time

from kundli_kombat.battle_math import score_battle
from kundli_kombat.ephemeris import calculate_chart


def _chart(dob: date) -> dict[str, object]:
    return calculate_chart(
        dob=dob, tob=time(12), tob_unknown=False,
        lat=28.6139, lon=77.2090, tz="Asia/Kolkata",
    )


def test_same_pair_produces_identical_round_scores() -> None:
    p1, p2 = _chart(date(1995, 4, 14)), _chart(date(1988, 11, 5))
    first = score_battle(p1, p2)
    for _ in range(3):
        assert score_battle(p1, p2) == first


def test_battle_has_five_stat_rounds_and_weighted_verdict() -> None:
    rounds, verdict, winner = score_battle(_chart(date(1995, 4, 14)), _chart(date(1989, 12, 13)))
    assert [item.name for item in rounds] == ["Love", "Career", "Luck", "Fire", "Chaos"]
    assert 0 <= verdict <= 100
    assert winner in {"p1", "p2", "tie"}
    assert all(0 <= item.p1_score <= 100 and 0 <= item.p2_score <= 100 for item in rounds)
