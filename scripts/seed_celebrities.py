#!/usr/bin/env python3
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from kundli_kombat.convex_client import mutation  # noqa: E402
from kundli_kombat.ephemeris import calculate_chart  # noqa: E402


async def main() -> None:
    seeds = json.loads((ROOT / "apps" / "api" / "data" / "celebrities.json").read_text())
    for seed in seeds:
        chart = calculate_chart(
            dob=date.fromisoformat(seed["dob"]),
            tob=None,
            tob_unknown=True,
            lat=seed["lat"],
            lon=seed["lon"],
            tz=seed["tz"],
        )
        celebrity_id = await mutation("celebrities:upsert", {
            "name": seed["name"],
            "dob": seed["dob"],
            "tobUnknown": True,
            "place": seed["place"],
            "sourceUrl": "seed:build-brief",
            "chart": chart,
            "big3": chart["big3"],
        })
        print(f"{seed['name']}: {celebrity_id} ({seed['timeLabel']})")


if __name__ == "__main__":
    asyncio.run(main())

