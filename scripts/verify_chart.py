#!/usr/bin/env python3
import argparse
import sys
from datetime import date, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from kundli_kombat.ephemeris import calculate_chart, verify_anchor  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Kundli Kombat's Lahiri chart pipeline")
    parser.add_argument("--dob")
    parser.add_argument("--tob")
    parser.add_argument("--place", default="Human acceptance test")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--tz")
    parser.add_argument("--expected-sun", default="—")
    parser.add_argument("--expected-moon", default="—")
    parser.add_argument("--expected-rising", default="—")
    parser.add_argument("--expected-nakshatra", default="—")
    args = parser.parse_args()

    anchor = verify_anchor()
    print("Astronomical anchor — 2000-01-01 12:00 UTC, Greenwich")
    print(f"Tropical Sun : {anchor.tropical_sun_longitude:8.3f}°  expected 280.46° ±0.2")
    print(f"Lahiri       : {anchor.lahiri_ayanamsa:8.3f}°  expected  23.87° ±0.1")
    print(f"Sidereal Sun : {anchor.sidereal_sun_longitude:8.3f}°  Sagittarius")

    supplied = [args.dob, args.tob, args.lat, args.lon, args.tz]
    if not any(value is not None for value in supplied):
        print("\nAdd --dob, --tob, --lat, --lon and --tz for the human acceptance chart.")
        return
    if not all(value is not None for value in supplied):
        parser.error("--dob, --tob, --lat, --lon and --tz are required together")

    chart = calculate_chart(
        dob=date.fromisoformat(args.dob),
        tob=time.fromisoformat(args.tob),
        tob_unknown=False,
        lat=args.lat,
        lon=args.lon,
        tz=args.tz,
    )
    print(f"\nHuman acceptance — {args.place}")
    print(f"{'Field':<14}{'App':<22}Drik Panchang")
    print("-" * 54)
    expected = {
        "Sun": args.expected_sun,
        "Moon": args.expected_moon,
        "Lagna": args.expected_rising,
        "Nakshatra": args.expected_nakshatra,
    }
    actual = {
        "Sun": chart["big3"]["sun"],
        "Moon": chart["big3"]["moon"],
        "Lagna": chart["big3"]["rising"],
        "Nakshatra": f"{chart['nakshatra']} (pada {chart['nakshatraPada']})",
    }
    for key in ("Sun", "Moon", "Lagna", "Nakshatra"):
        print(f"{key:<14}{actual[key]:<22}{expected[key]}")


if __name__ == "__main__":
    main()

