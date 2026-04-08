"""Field execution: did the visit happen, where and how well — and what's missing from the shelf?"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from merch.model import Plan, Point, Store, km

GEOFENCE_KM = 0.15  # GPS within 150 m of the store
MIN_VISIT_MINUTES = 20


@dataclass(frozen=True, slots=True)
class CheckIn:
    merchandiser_id: str
    store_id: str
    day: str
    at: datetime
    location: Point
    checkout_at: datetime | None = None
    photos: int = 0
    out_of_stock: tuple[str, ...] = ()  # SKUs missing from shelf
    skus_checked: int = 0


@dataclass(slots=True)
class VisitAudit:
    store_id: str
    day: str
    status: str  # "completed" | "missed" | "suspect"
    reasons: list[str] = field(default_factory=list)


def audit_visits(plan: Plan, checkins: list[CheckIn], stores: dict[str, Store]) -> list[VisitAudit]:
    """Match planned visits to check-ins. A visit counts only if the merchandiser was physically there
    (geofence), stayed long enough and left photo evidence. 'Suspect' visits go to a supervisor."""
    by_key = {(c.store_id, c.day): c for c in checkins}
    out: list[VisitAudit] = []
    for route in plan.routes:
        for v in route.visits:
            c = by_key.get((v.store_id, route.day))
            if c is None:
                out.append(VisitAudit(v.store_id, route.day, "missed", ["no check-in"]))
                continue
            reasons = []
            dist = km(c.location, stores[v.store_id].location)
            if dist > GEOFENCE_KM:
                reasons.append(f"checked in {dist * 1000:.0f} m from the store")
            if c.checkout_at is None:
                reasons.append("no check-out")
            elif (c.checkout_at - c.at).total_seconds() / 60 < MIN_VISIT_MINUTES:
                reasons.append(f"visit lasted {(c.checkout_at - c.at).total_seconds() / 60:.0f} min")
            if c.photos == 0:
                reasons.append("no shelf photos")
            if c.merchandiser_id != route.merchandiser_id:
                reasons.append("checked in by a different merchandiser")
            out.append(VisitAudit(v.store_id, route.day, "suspect" if reasons else "completed", reasons))
    return out


@dataclass(slots=True)
class Kpis:
    planned: int
    completed: int
    compliance: float
    osa: float  # on-shelf availability
    oos_by_sku: dict[str, int]
    oos_by_store: dict[str, list[str]]


def kpis(audits: list[VisitAudit], checkins: list[CheckIn]) -> Kpis:
    completed = {(a.store_id, a.day) for a in audits if a.status == "completed"}
    checked = oos = 0
    by_sku: dict[str, int] = defaultdict(int)
    by_store: dict[str, set[str]] = defaultdict(set)
    for c in checkins:
        if (c.store_id, c.day) not in completed:
            continue  # only trust stock data from verified visits
        checked += c.skus_checked
        oos += len(c.out_of_stock)
        for sku in c.out_of_stock:
            by_sku[sku] += 1
            by_store[c.store_id].add(sku)
    return Kpis(
        planned=len(audits),
        completed=len(completed),
        compliance=round(len(completed) / max(1, len(audits)), 3),
        osa=round(1 - oos / checked, 3) if checked else 1.0,
        oos_by_sku=dict(sorted(by_sku.items(), key=lambda kv: (-kv[1], kv[0]))),
        oos_by_store={k: sorted(v) for k, v in sorted(by_store.items())},
    )
