"""Cost and distance calculations. Pure functions, no database access.

Formulas are documented in docs/costs.md.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

RECURRENCE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}


# --- Inputs ---------------------------------------------------------------


@dataclass(frozen=True)
class RefuelData:
    id: str
    ts: datetime
    litres: float
    total: float
    full_tank: bool
    odometer_km: float | None = None


@dataclass(frozen=True)
class ChargeData:
    start_ts: datetime
    energy_kwh: float
    cost: float


@dataclass(frozen=True)
class OdometerData:
    ts: datetime
    odometer_km: float


@dataclass(frozen=True)
class MaintenanceData:
    date: date
    cost: float
    odometer_km: float | None = None


@dataclass(frozen=True)
class ExpenseData:
    date: date
    amount: float
    recurrence: str | None = None
    end_date: date | None = None


# --- Results --------------------------------------------------------------


@dataclass(frozen=True)
class OdoPoint:
    ts: datetime
    km: float


@dataclass(frozen=True)
class FuelInterval:
    """Consumption between two full-tank refuels (full-to-full)."""

    start: datetime
    end: datetime
    end_refuel_id: str
    litres: float
    km: float

    @property
    def l_per_100km(self) -> float:
        return self.litres / self.km * 100


@dataclass
class PeriodTotals:
    km: float = 0.0
    fuel_l: float = 0.0
    fuel_cost: float = 0.0
    electricity_kwh: float = 0.0
    electricity_cost: float = 0.0
    maintenance_cost: float = 0.0
    other_cost: float = 0.0
    refuel_count: int = 0
    charge_count: int = 0
    maintenance_count: int = 0
    # Full-to-full intervals that end in the period, for L/100 km.
    interval_l: float = 0.0
    interval_km: float = 0.0
    # Distance is only known up to the last odometer value.
    distance_known_until: datetime | None = field(default=None)

    @property
    def energy_cost(self) -> float:
        return self.fuel_cost + self.electricity_cost

    @property
    def total_cost(self) -> float:
        return self.energy_cost + self.maintenance_cost + self.other_cost

    @property
    def energy_cost_per_km(self) -> float | None:
        return self.energy_cost / self.km if self.km >= 1 else None

    @property
    def total_cost_per_km(self) -> float | None:
        return self.total_cost / self.km if self.km >= 1 else None

    @property
    def fuel_l_per_100km(self) -> float | None:
        return self.interval_l / self.interval_km * 100 if self.interval_km > 0 else None

    def __add__(self, other: "PeriodTotals") -> "PeriodTotals":
        known = [t for t in (self.distance_known_until, other.distance_known_until) if t]
        return PeriodTotals(
            km=self.km + other.km,
            fuel_l=self.fuel_l + other.fuel_l,
            fuel_cost=self.fuel_cost + other.fuel_cost,
            electricity_kwh=self.electricity_kwh + other.electricity_kwh,
            electricity_cost=self.electricity_cost + other.electricity_cost,
            maintenance_cost=self.maintenance_cost + other.maintenance_cost,
            other_cost=self.other_cost + other.other_cost,
            refuel_count=self.refuel_count + other.refuel_count,
            charge_count=self.charge_count + other.charge_count,
            maintenance_count=self.maintenance_count + other.maintenance_count,
            interval_l=self.interval_l + other.interval_l,
            interval_km=self.interval_km + other.interval_km,
            distance_known_until=min(known) if known else None,
        )

    def as_dict(self) -> dict:
        def r(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        return {
            "km": r(self.km, 1),
            "fuel_l": r(self.fuel_l, 2),
            "fuel_cost": r(self.fuel_cost, 2),
            "electricity_kwh": r(self.electricity_kwh, 2),
            "electricity_cost": r(self.electricity_cost, 2),
            "maintenance_cost": r(self.maintenance_cost, 2),
            "other_cost": r(self.other_cost, 2),
            "energy_cost": r(self.energy_cost, 2),
            "total_cost": r(self.total_cost, 2),
            "energy_cost_per_km": r(self.energy_cost_per_km, 3),
            "total_cost_per_km": r(self.total_cost_per_km, 3),
            "fuel_l_per_100km": r(self.fuel_l_per_100km, 2),
            "refuel_count": self.refuel_count,
            "charge_count": self.charge_count,
            "maintenance_count": self.maintenance_count,
            "distance_known_until": self.distance_known_until,
        }


# --- Date helpers ---------------------------------------------------------


# Local times are converted to UTC right away. Python compares and subtracts
# datetimes that share a tzinfo by wall clock, which is wrong across DST changes.


def local_midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(0), tzinfo=tz).astimezone(UTC)


def local_noon(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(12), tzinfo=tz).astimezone(UTC)


def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(day: date, months: int) -> date:
    """First day of the month ``months`` after the month of ``day``."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_ranges(last_day: date, count: int) -> list[tuple[date, date]]:
    """``count`` calendar months ending with the month of ``last_day``, as [start, end)."""
    first = add_months(last_day, -(count - 1))
    return [(add_months(first, i), add_months(first, i + 1)) for i in range(count)]


# --- Odometer and distance ------------------------------------------------


def build_odometer_points(points: Iterable[OdoPoint]) -> tuple[list[OdoPoint], int]:
    """Sort points and drop the ones that would make the odometer go backwards.

    Returns the clean list and the number of dropped points.
    """
    clean: list[OdoPoint] = []
    dropped = 0
    for point in sorted(points, key=lambda p: (p.ts, p.km)):
        if clean and point.km < clean[-1].km:
            dropped += 1
            continue
        if clean and point.ts == clean[-1].ts:
            clean[-1] = point  # same moment: keep the highest value
            continue
        clean.append(point)
    return clean, dropped


def distance_between(points: list[OdoPoint], start: datetime, end: datetime) -> float:
    """km driven in [start, end), interpolated linearly between known points."""
    start_s, end_s = start.timestamp(), end.timestamp()
    total = 0.0
    for a, b in pairwise(points):
        a_s, b_s = a.ts.timestamp(), b.ts.timestamp()
        lo, hi = max(a_s, start_s), min(b_s, end_s)
        if hi <= lo:
            continue
        total += (b.km - a.km) * (hi - lo) / (b_s - a_s)
    return total


# --- Fuel -----------------------------------------------------------------


def fuel_intervals(refuels: Iterable[RefuelData]) -> list[FuelInterval]:
    """Full-to-full consumption intervals.

    An interval starts at a full-tank refuel with an odometer value and ends at
    the next full-tank refuel with an odometer value. Litres of partial refuels
    in between count towards the interval. A full refuel without odometer breaks
    the chain, because the distance is unknown.
    """
    intervals: list[FuelInterval] = []
    anchor: RefuelData | None = None
    litres = 0.0
    for refuel in sorted(refuels, key=lambda r: r.ts):
        if anchor is None:
            if refuel.full_tank and refuel.odometer_km is not None:
                anchor = refuel
            continue
        litres += refuel.litres
        if not refuel.full_tank:
            continue
        if refuel.odometer_km is not None and refuel.odometer_km > anchor.odometer_km:
            intervals.append(
                FuelInterval(
                    start=anchor.ts,
                    end=refuel.ts,
                    end_refuel_id=refuel.id,
                    litres=litres,
                    km=refuel.odometer_km - anchor.odometer_km,
                )
            )
        anchor = refuel if refuel.odometer_km is not None else None
        litres = 0.0
    return intervals


# --- Expenses -------------------------------------------------------------


def expense_in_range(expense: ExpenseData, start: date, end: date, today: date) -> float:
    """Part of an expense that falls in [start, end).

    A recurring expense of amount A every n months adds A / n to each month from
    its start date until its end date (or until the current month), pro rata
    for months that are only partly inside the range.
    """
    if expense.recurrence is None:
        return expense.amount if start <= expense.date < end else 0.0

    per_month = expense.amount / RECURRENCE_MONTHS[expense.recurrence]
    last = min(expense.end_date or today, today)
    total = 0.0
    month = month_start(expense.date)
    while month <= last and month < end:
        next_month = add_months(month, 1)
        overlap = (min(next_month, end) - max(month, start)).days
        if overlap > 0:
            total += per_month * overlap / (next_month - month).days
        month = next_month
    return total


# --- Per-vehicle book -----------------------------------------------------


class VehicleBook:
    """All records of one vehicle, with period calculations."""

    def __init__(
        self,
        *,
        tz: ZoneInfo,
        today: date,
        start_date: date,
        start_odometer_km: float,
        refuels: Iterable[RefuelData] = (),
        charges: Iterable[ChargeData] = (),
        readings: Iterable[OdometerData] = (),
        maintenance: Iterable[MaintenanceData] = (),
        expenses: Iterable[ExpenseData] = (),
    ) -> None:
        self.tz = tz
        self.today = today
        self.refuels = sorted(refuels, key=lambda r: r.ts)
        self.charges = list(charges)
        self.maintenance = list(maintenance)
        self.expenses = list(expenses)

        raw_points = [OdoPoint(local_midnight(start_date, tz), start_odometer_km)]
        raw_points += [OdoPoint(r.ts, r.odometer_km) for r in readings]
        raw_points += [OdoPoint(r.ts, r.odometer_km) for r in self.refuels if r.odometer_km is not None]
        raw_points += [
            OdoPoint(local_noon(m.date, tz), m.odometer_km)
            for m in self.maintenance
            if m.odometer_km is not None
        ]
        self.points, self.dropped_points = build_odometer_points(raw_points)
        self.intervals = fuel_intervals(self.refuels)

    @property
    def latest_odometer(self) -> OdoPoint | None:
        return self.points[-1] if self.points else None

    def interval_by_refuel(self) -> dict[str, FuelInterval]:
        return {i.end_refuel_id: i for i in self.intervals}

    def period(self, start: date, end: date) -> PeriodTotals:
        """Totals for the local dates [start, end)."""
        start_ts, end_ts = local_midnight(start, self.tz), local_midnight(end, self.tz)
        totals = PeriodTotals(
            km=distance_between(self.points, start_ts, end_ts),
            distance_known_until=self.points[-1].ts if self.points else None,
        )
        for refuel in self.refuels:
            if start_ts <= refuel.ts < end_ts:
                totals.fuel_l += refuel.litres
                totals.fuel_cost += refuel.total
                totals.refuel_count += 1
        # Until trips exist (M3), electricity is counted when it is charged.
        for charge in self.charges:
            if start_ts <= charge.start_ts < end_ts:
                totals.electricity_kwh += charge.energy_kwh
                totals.electricity_cost += charge.cost
                totals.charge_count += 1
        for interval in self.intervals:
            if start_ts <= interval.end < end_ts:
                totals.interval_l += interval.litres
                totals.interval_km += interval.km
        for record in self.maintenance:
            if start <= record.date < end:
                totals.maintenance_cost += record.cost
                totals.maintenance_count += 1
        for expense in self.expenses:
            totals.other_cost += expense_in_range(expense, start, end, self.today)
        return totals

    def rolling_12_months(self) -> PeriodTotals:
        """The last 12 months up to and including today."""
        end = self.today + timedelta(days=1)
        return self.period(minus_year(end), end)


def minus_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)
