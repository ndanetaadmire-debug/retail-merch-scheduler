# retail-merch-scheduler

[![CI](https://github.com/ndanetaadmire-debug/retail-merch-scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/ndanetaadmire-debug/retail-merch-scheduler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![mypy](https://img.shields.io/badge/mypy-strict-2A6DB2)
![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)

**The planning engine behind a retail-execution app for FMCG field teams.** It builds each merchandiser's week of store visits, routes every day, and turns field check-ins into trustworthy compliance and stock-availability reports.

Generalised from the merchandiser scheduling and stock-reporting system I built for a Nestlé field-marketing team.

```
$ merch plan data/stores.json data/team.json
thabo Mon: Checkers Rosebank (0h15) → Pick n Pay Sandton City (1h25) → Shoprite Maponya Mall (3h16)  [drive 111 min, day 291 min]
thabo Tue: Spar Killarney (0h11) → Spar Melville (1h22)                                              [drive 33 min,  day 153 min]
thabo Wed: Checkers Rosebank (0h15) → Pick n Pay Sandton City (1h25) → Shoprite Maponya Mall (3h16)  [drive 111 min, day 291 min]
...
zanele Mon: Pick n Pay Fourways (0h09) → Checkers Midrand (1h37)                                     [drive 65 min,  day 185 min]
```

## Planning

| Rule | How |
|---|---|
| **Visit frequency by tier** | A = 3/week, B = 2, C = 1, sized by service time |
| **Territory** | Each store goes to the nearest merchandiser with the required **skill** (e.g. promo builds) and spare weekly capacity; A-tier stores are assigned first so they get the closest people |
| **Even spacing** | Visits are spread across the week (Mon/Wed/Fri for 3×); **never consecutive days** when avoidable; lighter days preferred |
| **Opening days** | A store open Mon/Wed/Fri is only scheduled on those days |
| **Routing** | Nearest-neighbour construction, then **2-opt** to remove crossings; round trip from home |
| **Working day** | If a day overruns, the lowest-priority stops are dropped and **reported**, never silently lost |
| **Explainability** | Everything unschedulable comes with a reason: missing skill, capacity, opening days, or the day being too long |

## Execution & reporting

A planned visit only counts as done if the merchandiser was actually there:

- **Geofenced check-in** within 150 m of the store
- **Check-out** and a minimum visit length
- **Shelf photo evidence**
- Checked in by the **assigned** merchandiser

Anything else is `missed` or `suspect` (with reasons) for a supervisor. **On-shelf availability (OSA)** and out-of-stock reports by SKU and store are computed **only from verified visits**, so a drive-by check-in can't pollute the stock data a sales team acts on.

## Tests

Tier frequencies met, no consecutive-day visits, skills, opening days and working-day limits respected, arrival times monotonic, 2-opt never worse than nearest-neighbour, unschedulable stores reported with reasons, compliance audit (missed / 1 km away / no photos), and KPIs computed only from verified visits.

```bash
pip install -e ".[dev]"
merch plan data/stores.json data/team.json
pytest --cov && mypy && ruff check src tests
```

Pure Python, zero runtime dependencies; swap `drive_minutes` for a routing API (OSRM, Google) when road-network accuracy matters.

---

Built by **[Admire T. Ndaneta](https://admire-portfolio.vercel.app)**. MIT licensed.
