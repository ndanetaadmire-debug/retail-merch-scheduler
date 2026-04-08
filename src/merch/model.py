from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum


class Tier(StrEnum):
    A = "A"  # high-volume: 3 visits / week
    B = "B"  # 2 visits / week
    C = "C"  # 1 visit / week


VISITS_PER_WEEK = {Tier.A: 3, Tier.B: 2, Tier.C: 1}
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lng: float


def km(a: Point, b: Point) -> float:
    r = 6371.0
    dlat, dlng = math.radians(b.lat - a.lat), math.radians(b.lng - a.lng)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(h))


def drive_minutes(a: Point, b: Point, kmh: float = 35.0, detour: float = 1.3) -> int:
    return math.ceil(km(a, b) * detour / kmh * 60)


@dataclass(frozen=True, slots=True)
class Store:
    id: str
    name: str
    location: Point
    tier: Tier
    service_minutes: int = 60
    open_days: tuple[str, ...] = DAYS
    needs_skill: str | None = None  # e.g. "promo_build"


@dataclass(frozen=True, slots=True)
class Merchandiser:
    id: str
    name: str
    home: Point
    work_days: tuple[str, ...] = DAYS[:5]
    minutes_per_day: int = 480
    skills: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True)
class Visit:
    store_id: str
    day: str
    seq: int = 0
    arrive_min: int = 0  # minutes after shift start


@dataclass(slots=True)
class DayRoute:
    merchandiser_id: str
    day: str
    visits: list[Visit]
    drive_minutes: int
    work_minutes: int


@dataclass(slots=True)
class Plan:
    routes: list[DayRoute]
    unscheduled: list[tuple[str, str]]  # (store_id, reason)

    def visits_for(self, store_id: str) -> list[str]:
        return [r.day for r in self.routes for v in r.visits if v.store_id == store_id]
