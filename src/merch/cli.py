"""merch plan data/stores.json data/team.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from merch.model import Merchandiser, Point, Store, Tier
from merch.scheduler import plan_week


def load(stores_path: Path, team_path: Path) -> tuple[list[Store], list[Merchandiser]]:
    stores = [
        Store(
            s["id"],
            s["name"],
            Point(*s["location"]),
            Tier(s["tier"]),
            s.get("service_minutes", 60),
            tuple(s.get("open_days", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])),
            s.get("needs_skill"),
        )
        for s in json.loads(stores_path.read_text())
    ]
    team = [
        Merchandiser(
            m["id"],
            m["name"],
            Point(*m["home"]),
            tuple(m.get("work_days", ["Mon", "Tue", "Wed", "Thu", "Fri"])),
            m.get("minutes_per_day", 480),
            frozenset(m.get("skills", [])),
        )
        for m in json.loads(team_path.read_text())
    ]
    return stores, team


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="merch")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("stores", type=Path)
    pl.add_argument("team", type=Path)
    a = p.parse_args(argv)
    stores, team = load(a.stores, a.team)
    plan = plan_week(stores, team)
    names = {s.id: s.name for s in stores}
    for r in plan.routes:
        stops = " → ".join(f"{names[v.store_id]} ({v.arrive_min // 60}h{v.arrive_min % 60:02d})" for v in r.visits)
        print(f"{r.merchandiser_id} {r.day}: {stops}  [drive {r.drive_minutes} min, day {r.work_minutes} min]")
    for sid, why in plan.unscheduled:
        print(f"  ! {names[sid]}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
