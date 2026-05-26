import itertools
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from merch.cli import load, main
from merch.compliance import CheckIn, audit_visits, kpis
from merch.model import DAYS, VISITS_PER_WEEK, Merchandiser, Point, Store, Tier
from merch.scheduler import _nearest_neighbour, _tour, _two_opt, plan_week

STORES, TEAM = load(Path("data/stores.json"), Path("data/team.json"))
BY_ID = {s.id: s for s in STORES}


@pytest.fixture(scope="module")
def plan():  # type: ignore[no-untyped-def]
    return plan_week(STORES, TEAM)


def test_every_store_gets_its_tier_frequency(plan) -> None:  # type: ignore[no-untyped-def]
    assert plan.unscheduled == []
    for s in STORES:
        assert len(plan.visits_for(s.id)) == VISITS_PER_WEEK[s.tier], s.id


def test_multi_visit_stores_are_never_visited_on_consecutive_days(plan) -> None:  # type: ignore[no-untyped-def]
    for s in STORES:
        idx = sorted(DAYS.index(d) for d in plan.visits_for(s.id))
        assert all(b - a >= 2 for a, b in itertools.pairwise(idx)), (s.id, idx)


def test_constraints_skill_opening_days_and_working_day(plan) -> None:  # type: ignore[no-untyped-def]
    team = {m.id: m for m in TEAM}
    for r in plan.routes:
        assert r.work_minutes <= team[r.merchandiser_id].minutes_per_day
        assert r.day in team[r.merchandiser_id].work_days
        for v in r.visits:
            s = BY_ID[v.store_id]
            assert r.day in s.open_days
            if s.needs_skill:
                assert s.needs_skill in team[r.merchandiser_id].skills
    assert set(plan.visits_for("chk-midrand")) <= {"Mon", "Wed", "Fri"}


def test_arrival_times_increase_along_the_route(plan) -> None:  # type: ignore[no-untyped-def]
    for r in plan.routes:
        times = [v.arrive_min for v in r.visits]
        assert times == sorted(times) and [v.seq for v in r.visits] == list(range(1, len(times) + 1))


def test_two_opt_never_worse_than_nearest_neighbour() -> None:
    home = Point(-26.2, 28.04)
    stops = [
        Store(f"s{i}", f"S{i}", Point(-26.2 + (i % 3) * 0.05, 28.0 + (i * 7 % 5) * 0.04), Tier.C) for i in range(8)
    ]
    nn = _nearest_neighbour(home, stops)
    assert _tour(home, _two_opt(home, nn)) <= _tour(home, nn)


def test_reports_what_it_cannot_schedule() -> None:
    far = [Store(f"x{i}", f"X{i}", Point(-26.0 - i * 0.3, 28.0), Tier.A, service_minutes=240) for i in range(4)]
    plan = plan_week(
        [*far, Store("promo", "P", Point(-26.1, 28.0), Tier.C, needs_skill="promo_build")],
        [Merchandiser("m", "M", Point(-26.0, 28.0))],
    )
    reasons = dict(plan.unscheduled)
    assert reasons["promo"] == "no merchandiser has the required skill"
    assert any("capacity" in r or "does not fit" in r for r in reasons.values())


def test_compliance_audit_and_kpis(plan) -> None:  # type: ignore[no-untyped-def]
    t0 = datetime(2026, 11, 16, 9, 0)
    visits = [(r, v) for r in plan.routes for v in r.visits]
    checkins = []
    for i, (r, v) in enumerate(visits):
        if i == 0:
            continue  # missed
        s = BY_ID[v.store_id]
        loc = Point(s.location.lat + (0.01 if i == 1 else 0), s.location.lng)  # i==1: ~1.1 km away
        checkins.append(
            CheckIn(
                r.merchandiser_id,
                v.store_id,
                r.day,
                t0,
                loc,
                t0 + timedelta(minutes=45),
                photos=0 if i == 2 else 3,
                out_of_stock=("NESCAFE-200G",) if i % 4 == 0 else (),
                skus_checked=20,
            )
        )
    audits = audit_visits(plan, checkins, BY_ID)
    status = [a.status for a in audits]
    assert status[0] == "missed"
    assert status[1] == "suspect" and "m from the store" in audits[1].reasons[0]
    assert status[2] == "suspect" and audits[2].reasons == ["no shelf photos"]
    k = kpis(audits, checkins)
    assert k.planned == len(visits) and k.completed == len(visits) - 3
    assert 0.9 < k.osa < 1.0 and "NESCAFE-200G" in k.oos_by_sku


def test_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["plan", "data/stores.json", "data/team.json"]) == 0
    assert "thabo Mon:" in capsys.readouterr().out
