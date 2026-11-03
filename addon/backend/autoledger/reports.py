"""Report figures built from the ledger: grouped periods, comparisons and trends.

Every figure is a sum of ``PeriodTotals``, so reports follow the same rules as
the overview (docs/costs.md).
"""

from datetime import date, timedelta
from functools import reduce
from operator import add

from .ledger import PeriodTotals, VehicleBook, add_months, month_start

GROUPS = ("month", "quarter", "year", "none")
# Meteorological seasons, by month number.
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_ORDER = ("winter", "spring", "summer", "autumn")
MAX_GROUPS = 400


def _group_start(day: date, group: str) -> date:
    if group == "year":
        return date(day.year, 1, 1)
    if group == "quarter":
        return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)
    return month_start(day)


def _group_label(start: date, group: str) -> str:
    if group == "year":
        return str(start.year)
    if group == "quarter":
        return f"{start.year}-Q{(start.month - 1) // 3 + 1}"
    return start.strftime("%Y-%m")


def group_ranges(start: date, end: date, group: str) -> list[tuple[str, date, date]]:
    """Calendar groups covering the local dates [start, end), clipped to that range."""
    if group == "none":
        return [("total", start, end)]
    step = {"month": 1, "quarter": 3, "year": 12}[group]
    ranges = []
    current = _group_start(start, group)
    while current < end and len(ranges) < MAX_GROUPS:
        following = add_months(current, step)
        ranges.append((_group_label(current, group), max(current, start), min(following, end)))
        current = following
    return ranges


def counted_days(start: date, end: date, today: date) -> int:
    """Days of [start, end) that have happened: recurring costs are only counted up to today."""
    return max((min(end, today + timedelta(days=1)) - start).days, 0)


def per_year(totals: PeriodTotals, days: int) -> dict:
    """Totals scaled to a year, for comparing periods of different length."""
    if days < 28:
        return {"km": None, "total_cost": None, "energy_cost": None, "maintenance_cost": None, "other_cost": None,
                "depreciation_cost": None}
    factor = 365.25 / days
    return {
        "km": round(totals.km * factor),
        "total_cost": round(totals.total_cost * factor, 2),
        "energy_cost": round(totals.energy_cost * factor, 2),
        "maintenance_cost": round(totals.maintenance_cost * factor, 2),
        "other_cost": round(totals.other_cost * factor, 2),
        "depreciation_cost": round(totals.depreciation_cost * factor, 2),
    }


def history_start(book: VehicleBook, start_date: date) -> date:
    """First month with data: the vehicle's start, or its earliest record before that."""
    candidates = [start_date]
    candidates += [r.ts.astimezone(book.tz).date() for r in book.refuels[:1]]
    candidates += [t.start_ts.astimezone(book.tz).date() for t in book.trips[:1]]
    candidates += [m.date for m in book.maintenance]
    return month_start(min(candidates))


def seasons(book: VehicleBook, first: date) -> dict:
    """Consumption per season, summed over every month since ``first``."""
    per_season: dict[str, list[PeriodTotals]] = {name: [] for name in SEASON_ORDER}
    current = month_start(first)
    stop = add_months(book.today, 1)
    while current < stop:
        per_season[SEASONS[current.month]].append(book.period(current, add_months(current, 1)))
        current = add_months(current, 1)
    result = {}
    for name in SEASON_ORDER:
        totals = reduce(add, per_season[name], PeriodTotals())
        result[name] = {
            "months": len(per_season[name]),
            "km": round(totals.km, 1),
            "trip_km": round(totals.trip_km, 1),
            "kwh_per_100km": _r(totals.kwh_per_100km, 1),
            "fuel_l_per_100km": _r(totals.fuel_l_per_100km, 2),
            "energy_cost_per_km": _r(totals.energy_cost_per_km, 3),
            "electric_share": _r(totals.electric_share, 3),
            "idle_kwh": round(totals.idle_kwh, 2),
        }
    return result


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
