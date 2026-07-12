from datetime import date, time

import pytest

from kundli_kombat.ephemeris import calculate_chart, verify_anchor


def test_greenwich_astronomical_anchor() -> None:
    anchor = verify_anchor()
    assert anchor.tropical_sun_longitude == pytest.approx(280.46, abs=0.2)
    assert anchor.lahiri_ayanamsa == pytest.approx(23.87, abs=0.1)
    assert anchor.sidereal_sun_longitude == pytest.approx(256.6, abs=0.3)


def test_unknown_birth_time_is_honest_solar_chart() -> None:
    chart = calculate_chart(
        dob=date(1988, 11, 5), tob=None, tob_unknown=True,
        lat=28.6139, lon=77.2090, tz="Asia/Kolkata",
    )
    assert chart["chartMode"] == "solar"
    assert chart["timeApproximate"] is True
    assert chart["ascendantLongitude"] is None
    assert chart["houses"] is None
    assert chart["big3"]["rising"] == "Solar chart"


def test_same_birth_data_is_deterministic() -> None:
    kwargs = dict(
        dob=date(2000, 1, 1), tob=time(12), tob_unknown=False,
        lat=51.4769, lon=0.0, tz="UTC",
    )
    assert calculate_chart(**kwargs) == calculate_chart(**kwargs)

