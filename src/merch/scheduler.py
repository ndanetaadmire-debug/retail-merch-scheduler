"""Weekly planner.

1. Territory: assign each store to the nearest merchandiser who has the required skill and spare
   weekly capacity (largest/most-visited stores first, so A-tier stores get the closest people).
2. Day pattern: spread each store's visits across the week (3/week → Mon/Wed/Fri style), skipping
   days the store is closed or the merchandiser is off, and never on consecutive days when avoidable.
3. Routing: per merchandiser per day, order stops with nearest-neighbour then improve with 2-opt,
   then drop the lowest-priority stops if the day overruns (reported, never silently).
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from collections.abc import Sequence

from merch.model import DAYS, VISITS_PER_WEEK, DayRoute, Merchandiser, Plan, Point, Store, Tier, Visit, drive_minutes

TIER_PRIORITY = {Tier.A: 0, Tier.B: 1, Tier.C: 2}


def plan_week(stores: Sequence[Store], team: Sequence[Merchandiser]) -> Plan:
    unscheduled: list[tuple[str, str]] = []
    weekly_capacity = {m.id: len(m.work_days) * m.minutes_per_day for m in team}
    load: dict[str, int] = defaultdict(int)
    territory: dict[str, list[Store]] = defaultdict(list)

    for s in sorted(stores, key=lambda s: (TIER_PRIORITY[s.tier], s.id)):
        need = VISITS_PER_WEEK[s.tier] * (s.service_minutes + 30)  # +30 ≈ average travel per stop
        candidates = [
            m
            for m in team
            if (s.needs_skill is None or s.needs_skill in m.skills)
            and load[m.id] + need <= weekly_capacity[m.id]
            and set(m.work_days) & set(s.open_days)
        ]
        if not candidates:
            reason = (
                "no merchandiser has the required skill"
                if s.needs_skill and not any(s.needs_skill in m.skills for m in team)
                else "team capacity exhausted"
            )
            unscheduled.append((s.id, reason))
            continue
        m = min(candidates, key=lambda m: drive_minutes(m.home, s.location))
        territory[m.id].append(s)
        load[m.id] += need

    by_day: dict[tuple[str, str], list[Store]] = defaultdict(list)
    for m in team:
        for s in territory[m.id]:
            days = spread_days(
                VISITS_PER_WEEK[s.tier], [d for d in DAYS if d in m.work_days and d in s.open_days], by_day, m.id
            )
            if len(days) < VISITS_PER_WEEK[s.tier]:
                unscheduled.append((s.id, f"only {len(days)} of {VISITS_PER_WEEK[s.tier]} visits fit the opening days"))
            for d in days:
                by_day[(m.id, d)].append(s)

    routes: list[DayRoute] = []
    team_by_id = {m.id: m for m in team}
    for (mid, day), day_stores in sorted(by_day.items(), key=lambda kv: (kv[0][0], DAYS.index(kv[0][1]))):
        m = team_by_id[mid]
        route, dropped = build_route(m, day_stores)
        unscheduled.extend((sid, f"{day}: does not fit in the working day") for sid in dropped)
        routes.append(DayRoute(mid, day, route, *_route_cost(m, route, {s.id: s for s in day_stores})))
    return Plan(routes, unscheduled)


def spread_days(n: int, allowed: list[str], by_day: dict[tuple[str, str], list[Store]], mid: str) -> list[str]:
    """Pick n days as evenly spaced as possible, preferring lighter days; avoid consecutive days when n < len/2."""
    if n >= len(allowed):
        return allowed[:n] if n <= len(allowed) else allowed
    best: list[str] | None = None
    best_score = float("inf")
    idx = [DAYS.index(d) for d in allowed]

    def choose(start: int, picked: list[int]) -> None:
        nonlocal best, best_score
        if len(picked) == n:
            gaps = [b - a for a, b in itertools.pairwise(picked)]
            consecutive = sum(g == 1 for g in gaps)
            unevenness = (max(gaps) - min(gaps)) if gaps else 0
            busy = sum(len(by_day[(mid, DAYS[i])]) for i in picked)
            score = consecutive * 100 + unevenness * 10 + busy
            if score < best_score:
                best_score, best = score, [DAYS[i] for i in picked]
            return
        for k in range(start, len(idx)):
            choose(k + 1, [*picked, idx[k]])

    choose(0, [])
    return best or []


def build_route(m: Merchandiser, stores: list[Store]) -> tuple[list[Visit], list[str]]:
    order = _nearest_neighbour(m.home, stores)
    order = _two_opt(m.home, order)
    dropped: list[str] = []
    lookup = {s.id: s for s in stores}
    while order and _route_cost(m, [Visit(s.id, "") for s in order], lookup)[1] > m.minutes_per_day:
        victim = max(order, key=lambda s: (TIER_PRIORITY[s.tier], drive_minutes(m.home, s.location)))
        order.remove(victim)
        dropped.append(victim.id)
    visits, t, pos = [], 0, m.home
    for i, s in enumerate(order):
        t += drive_minutes(pos, s.location)
        visits.append(Visit(s.id, "", seq=i + 1, arrive_min=t))
        t += s.service_minutes
        pos = s.location
    return visits, dropped


def _route_cost(m: Merchandiser, visits: list[Visit], stores: dict[str, Store]) -> tuple[int, int]:
    pos, drive, work = m.home, 0, 0
    for v in visits:
        s = stores[v.store_id]
        drive += drive_minutes(pos, s.location)
        work += s.service_minutes
        pos = s.location
    drive += drive_minutes(pos, m.home)
    return drive, drive + work


def _nearest_neighbour(start: Point, stores: list[Store]) -> list[Store]:
    left, out, pos = list(stores), [], start
    while left:
        nxt = min(left, key=lambda s: (drive_minutes(pos, s.location), s.id))
        out.append(nxt)
        left.remove(nxt)
        pos = nxt.location
    return out


def _tour(start: Point, order: list[Store]) -> int:
    pts = [start, *(s.location for s in order), start]
    return sum(drive_minutes(a, b) for a, b in itertools.pairwise(pts))


def _two_opt(start: Point, order: list[Store]) -> list[Store]:
    """Reverse segments while it shortens the round trip. Removes the crossings nearest-neighbour leaves."""
    best = order[:]
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best) + 1):
                cand = best[:i] + best[i:j][::-1] + best[j:]
                if _tour(start, cand) < _tour(start, best):
                    best, improved = cand, True
    return best
