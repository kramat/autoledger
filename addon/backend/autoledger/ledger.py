"""Cost and distance calculations. Pure functions, no database access.

Formulas are documented in docs/costs.md.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from statistics import median
from zoneinfo import ZoneInfo

RECURRENCE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
ELECTRIC_L_PER_KM = 0.05  # a trip below 0.5 L per 10 km counts as electric


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
    id: str = ""
    end_ts: datetime | None = None
    kind: str = "manual"
    soc_start: float | None = None
    soc_end: float | None = None


@dataclass(frozen=True)
class TripData:
    """A trip, or an idle record (``idle=True``, no distance)."""

    id: str
    start_ts: datetime
    end_ts: datetime
    distance_km: float = 0.0
    battery_start_pct: float | None = None
    battery_used_pct: float | None = None
    charged_kwh: float = 0.0  # charged within the trip's window, used on top of the % drop
    energy_kwh: float | None = None  # set by the user: used as is
    fuel_start_l: float | None = None
    fuel_end_l: float | None = None
    fuel_l: float = 0.0  # measured: max(start - end, 0)
    fuel_locked: bool = False
    idle: bool = False


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
    # From the first trip on, energy is counted when it is used (trips and idle),
    # valued at the battery / tank cost basis. See docs/costs.md.
    trip_count: int = 0
    trip_km: float = 0.0
    trip_kwh: float = 0.0
    trip_fuel_l: float = 0.0
    trip_cost: float = 0.0
    electric_km: float = 0.0
    idle_kwh: float = 0.0
    idle_fuel_l: float = 0.0
    idle_cost: float = 0.0
    purchase_energy_cost: float = 0.0  # energy counted on purchase (before the first trip)

    @property
    def trip_based(self) -> bool:
        """All energy in this period is counted per trip, so trip figures are complete."""
        return self.trip_km >= 1 and self.purchase_energy_cost == 0

    @property
    def kwh_per_100km(self) -> float | None:
        return max(self.trip_kwh, 0) / self.trip_km * 100 if self.trip_km >= 1 else None

    @property
    def electric_share(self) -> float | None:
        return self.electric_km / self.trip_km if self.trip_km >= 1 else None

    @property
    def energy_cost(self) -> float:
        return self.fuel_cost + self.electricity_cost

    @property
    def total_cost(self) -> float:
        return self.energy_cost + self.maintenance_cost + self.other_cost

    @property
    def energy_cost_per_km(self) -> float | None:
        if self.trip_based:
            return self.trip_cost / self.trip_km  # driving only: climate & standby excluded
        return self.energy_cost / self.km if self.km >= 1 else None

    @property
    def total_cost_per_km(self) -> float | None:
        return self.total_cost / self.km if self.km >= 1 else None

    @property
    def fuel_l_per_100km(self) -> float | None:
        if self.trip_based:
            return self.trip_fuel_l / self.trip_km * 100
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
            trip_count=self.trip_count + other.trip_count,
            trip_km=self.trip_km + other.trip_km,
            trip_kwh=self.trip_kwh + other.trip_kwh,
            trip_fuel_l=self.trip_fuel_l + other.trip_fuel_l,
            trip_cost=self.trip_cost + other.trip_cost,
            electric_km=self.electric_km + other.electric_km,
            idle_kwh=self.idle_kwh + other.idle_kwh,
            idle_fuel_l=self.idle_fuel_l + other.idle_fuel_l,
            idle_cost=self.idle_cost + other.idle_cost,
            purchase_energy_cost=self.purchase_energy_cost + other.purchase_energy_cost,
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
            "trip_count": self.trip_count,
            "trip_km": r(self.trip_km, 1),
            "trip_kwh": r(self.trip_kwh, 2),
            "trip_fuel_l": r(self.trip_fuel_l, 2),
            "trip_cost": r(self.trip_cost, 2),
            "kwh_per_100km": r(self.kwh_per_100km, 1),
            "electric_share": r(self.electric_share, 3),
            "idle_kwh": r(self.idle_kwh, 2),
            "idle_fuel_l": r(self.idle_fuel_l, 2),
            "idle_cost": r(self.idle_cost, 2),
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


# --- kWh per percent ------------------------------------------------------

LEARN_MIN_PCT = 20  # a session must add at least this much battery to learn from
LEARN_SESSIONS = 10
LEARN_MIN_SESSIONS = 3
CHARGE_EFFICIENCY = 0.90
LEARN_PLAUSIBLE = (0.6, 1.6)  # a session far from the capacity-based value is a bad reading
RECONCILE_MIN_COVERAGE = 0.8  # share of the odometer km between full tanks that trips must cover
FUEL_JUMP_L = 3.0  # a rise this large without a refuel record still starts a new stretch of the tank level


@dataclass(frozen=True)
class Factor:
    """Wall kWh per battery % at some moment, and where the value comes from."""

    value: float
    mode: str  # manual | learned | default
    sessions: tuple[str, ...] = ()


class FactorModel:
    """Manual value, else the median of the last home sessions, else from capacity."""

    def __init__(self, manual: float | None, battery_usable_kwh: float | None, charges: Iterable[ChargeData]):
        self.manual = manual
        self.default = battery_usable_kwh / 100 / CHARGE_EFFICIENCY if battery_usable_kwh else None
        samples = [
            (c.end_ts or c.start_ts, c.energy_kwh / (c.soc_end - c.soc_start), c.id)
            for c in charges
            if c.kind == "home" and c.soc_start is not None and c.soc_end is not None
            and c.soc_end - c.soc_start >= LEARN_MIN_PCT and c.energy_kwh > 0
        ]
        if self.default:
            low, high = (self.default * bound for bound in LEARN_PLAUSIBLE)
            samples = [s for s in samples if low <= s[1] <= high]
        self.samples = sorted(samples, key=lambda sample: sample[0])

    def at(self, ts: datetime | None = None) -> Factor | None:
        """The factor valid at ``ts`` (None: now). Only sessions finished by then count."""
        if self.manual:
            return Factor(self.manual, "manual")
        learned = self.learned(ts)
        if learned is not None:
            return learned
        return Factor(round(self.default, 4), "default") if self.default else None

    def learned(self, ts: datetime | None = None) -> Factor | None:
        usable = [s for s in self.samples if ts is None or s[0] <= ts][-LEARN_SESSIONS:]
        if len(usable) < LEARN_MIN_SESSIONS:
            return None
        return Factor(round(median(s[1] for s in usable), 4), "learned", tuple(s[2] for s in usable))


# --- Battery and tank cost basis --------------------------------------------


@dataclass
class TripCost:
    """How one trip or idle record was costed (also its explanation in the GUI)."""

    energy_kwh: float = 0.0
    factor: Factor | None = None
    kwh_price: float | None = None
    electricity_cost: float = 0.0
    fuel_l_measured: float = 0.0  # raw drop of the gauge
    fuel_l_provisional: float = 0.0  # after smoothing the gauge noise
    fuel_l: float = 0.0  # what is costed: reconciled at a full tank, else provisional
    fuel_reconciled: bool = False
    l_price: float | None = None
    fuel_cost: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def cost(self) -> float:
        return self.electricity_cost + self.fuel_cost

    def as_dict(self) -> dict:
        def r(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        return {
            "energy_kwh": round(self.energy_kwh, 3),
            "kwh_per_pct": self.factor.value if self.factor else None,
            "factor_mode": self.factor.mode if self.factor else None,
            "kwh_price": r(self.kwh_price, 4),
            "electricity_cost": round(self.electricity_cost, 3),
            "fuel_l_measured": round(self.fuel_l_measured, 2),
            "fuel_l_provisional": round(self.fuel_l_provisional, 2),
            "fuel_l": round(self.fuel_l, 2),
            "fuel_reconciled": self.fuel_reconciled,
            "l_price": r(self.l_price, 4),
            "fuel_cost": round(self.fuel_cost, 3),
            "cost": round(self.cost, 2),
            "notes": self.notes,
        }


class Pool:
    """Energy in the battery or the tank, with its weighted average cost."""

    def __init__(self, amount: float, price: float) -> None:
        self.amount = max(amount, 0.0)
        self.cost = self.amount * price
        self.default_price = price

    @property
    def price(self) -> float:
        return self.cost / self.amount if self.amount > 1e-9 else self.default_price

    def add(self, amount: float, cost: float) -> None:
        self.amount += amount
        self.cost += cost

    def take(self, amount: float) -> tuple[float, float, bool]:
        """Remove ``amount``: (cost, average price, ran short). A shortfall is priced at the default."""
        if amount <= 0:
            return 0.0, self.price, False
        price = self.price
        covered = min(amount, self.amount)
        cost = covered * price + (amount - covered) * self.default_price
        self.cost = max(self.cost - covered * price, 0.0)
        self.amount -= covered
        return cost, cost / amount, covered < amount - 1e-6


def _non_increasing_fit(values: list[float]) -> list[float]:
    """The non-increasing sequence closest to ``values`` (least squares, pool adjacent violators)."""
    blocks: list[list[float]] = []  # [sum, count] of runs that share one fitted value
    for value in values:
        blocks.append([value, 1])
        while len(blocks) > 1 and blocks[-1][0] / blocks[-1][1] > blocks[-2][0] / blocks[-2][1]:
            total, count = blocks.pop()
            blocks[-1][0] += total
            blocks[-1][1] += count
    return [total / count for total, count in blocks for _ in range(int(count))]


def smooth_fuel(trips: list[TripData], refuels: list[RefuelData]) -> dict[str, float]:
    """Fuel used per trip and idle record, from a tank level that can only go down between refuels.

    Fuel gauges are noisy: a reading 0.4 L too low on one report is 0.4 L too high
    on the next. Every report's level (each trip's and idle record's start and end) is
    fitted with the closest non-increasing line per stretch between refuels, and a
    record gets the drop of that line instead of the raw drop. Costs are replayed on
    every request, so later reports revise earlier trips: a dip that comes back is
    returned bit by bit. See docs/costs.md#fuel-gauge-noise.
    """
    readings: dict[datetime, float] = {}
    for t in trips:
        if not t.fuel_locked:
            for ts, level in ((t.start_ts, t.fuel_start_l), (t.end_ts, t.fuel_end_l)):
                if level is not None:
                    readings[ts] = level
    points = sorted(readings.items())
    refuel_times = sorted(r.ts for r in refuels)

    # A refuel, or a rise too large for noise (a refuel the user deleted), starts a new stretch.
    segment_of: dict[datetime, int] = {}
    fitted: dict[datetime, float] = {}
    stretch: list[tuple[datetime, float]] = []
    segment = 0

    def close() -> None:
        for (ts, _level), value in zip(stretch, _non_increasing_fit([level for _ts, level in stretch])):
            fitted[ts], segment_of[ts] = value, segment

    for ts, level in points:
        if stretch:
            prev_ts, prev_level = stretch[-1]
            refuelled = any(prev_ts < r <= ts for r in refuel_times)
            if refuelled or level - prev_level >= FUEL_JUMP_L:
                close()
                stretch, segment = [], segment + 1
        stretch.append((ts, level))
    if stretch:
        close()

    result: dict[str, float] = {}
    for t in trips:
        start, end = t.start_ts, t.end_ts
        if t.fuel_locked or start not in fitted or end not in fitted:
            continue
        # Across a refuel the drop is hidden in the refuel's estimate: provisional 0 until the full tank.
        result[t.id] = max(fitted[start] - fitted[end], 0.0) if segment_of[start] == segment_of[end] else 0.0
    return result


def reconcile_fuel(trips: list[TripData], refuels: list[RefuelData], provisional: dict[str, float]) -> dict[str, float]:
    """Litres per trip after spreading each full-to-full difference over the trips that used fuel.

    Between two full-tank refuels the true use is the litres refuelled in between
    (the closing refuel included). The difference with the provisional trip and idle
    litres is spread over the trips in proportion to their provisional litres, so a
    PHEV trip that ran on electricity stays at 0. Only when no trip shows any fuel
    use is it spread by distance.

    Only intervals whose trips cover most of the odometer distance are reconciled:
    when drives are missing (HA was down), their fuel must not land on the others.
    """
    result: dict[str, float] = {}
    # A full tank before the first trip is a valid start: only the trips after it are corrected.
    full = [r for r in refuels if r.full_tank and r.odometer_km is not None]
    for a, b in pairwise(full):
        window = [t for t in trips if a.ts < t.end_ts <= b.ts]
        true_l = sum(r.litres for r in refuels if a.ts < r.ts <= b.ts)
        litres = {t.id: provisional.get(t.id, t.fuel_l) for t in window}
        fixed = sum(litres[t.id] for t in window if t.idle or t.fuel_locked)
        spread = [t for t in window if not t.idle and not t.fuel_locked]
        km = sum(t.distance_km for t in spread)
        driven = b.odometer_km - a.odometer_km
        if km <= 0 or driven <= 0 or sum(t.distance_km for t in window) < RECONCILE_MIN_COVERAGE * driven:
            continue
        used = sum(litres[t.id] for t in spread)
        diff = true_l - fixed - used
        for trip in spread:
            share = litres[trip.id] / used if used > 0 else trip.distance_km / km
            result[trip.id] = max(litres[trip.id] + diff * share, 0.0)
    return result


def cost_trips(
    trips: list[TripData],
    charges: list[ChargeData],
    refuels: list[RefuelData],
    factors: FactorModel,
    kwh_price: float,
    l_price: float,
) -> dict[str, TripCost]:
    """Replay purchases and use in time order through the battery and tank pools.

    The pools start at the first trip with what the car had on board then, valued
    at the default prices.
    """
    if not trips:
        return {}
    first = trips[0]
    since = first.start_ts
    factor = factors.at(since)
    battery = Pool((first.battery_start_pct or 0) * factor.value if factor else 0.0, kwh_price)
    tank = Pool(first.fuel_start_l or 0.0, l_price)
    smoothed = smooth_fuel(trips, refuels)
    reconciled = reconcile_fuel(trips, refuels, smoothed)

    # Use goes before a purchase at the same moment: a refuel seen at the end of a trip came after it.
    timeline: list[tuple[datetime, int, object]] = [(t.end_ts, 0, t) for t in trips]
    timeline += [(c.end_ts or c.start_ts, 1, c) for c in charges if c.start_ts >= since]
    timeline += [(r.ts, 1, r) for r in refuels if r.ts >= since]
    timeline.sort(key=lambda item: (item[0], item[1]))

    result: dict[str, TripCost] = {}
    for _ts, _order, item in timeline:
        if isinstance(item, ChargeData):
            battery.add(item.energy_kwh, item.cost)
            continue
        if isinstance(item, RefuelData):
            tank.add(item.litres, item.total)
            continue
        trip: TripData = item
        cost = TripCost(fuel_l_measured=trip.fuel_l, fuel_l_provisional=smoothed.get(trip.id, trip.fuel_l))
        if trip.energy_kwh is not None:
            cost.energy_kwh = trip.energy_kwh
            cost.notes.append("energy set by hand")
        elif trip.battery_used_pct is not None:
            cost.factor = factors.at(trip.start_ts)
            cost.energy_kwh = (trip.battery_used_pct * cost.factor.value if cost.factor else 0.0) + trip.charged_kwh
            if trip.charged_kwh:
                cost.notes.append(f"includes {trip.charged_kwh:.2f} kWh charged in between")
        if cost.energy_kwh >= 0:
            cost.electricity_cost, cost.kwh_price, short = battery.take(cost.energy_kwh)
            if short:
                cost.notes.append("battery cost basis ran empty: the rest is priced at the default")
        else:
            battery.add(-cost.energy_kwh, 0.0)  # charged by the engine: its cost is in the fuel
            cost.kwh_price = 0.0
            cost.notes.append("battery charged by the engine")
        cost.fuel_l = reconciled.get(trip.id, cost.fuel_l_provisional)
        cost.fuel_reconciled = trip.id in reconciled
        cost.fuel_cost, cost.l_price, short = tank.take(cost.fuel_l)
        if short:
            cost.notes.append("tank cost basis ran empty: the rest is priced at the default")
        result[trip.id] = cost
    return result


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
        trips: Iterable[TripData] = (),
        kwh_per_pct: float | None = None,
        battery_usable_kwh: float | None = None,
        default_kwh_price: float = 0.25,
        default_l_price: float = 2.00,
    ) -> None:
        self.tz = tz
        self.today = today
        self.refuels = sorted(refuels, key=lambda r: r.ts)
        self.charges = list(charges)
        self.maintenance = list(maintenance)
        self.expenses = list(expenses)
        self.trips = sorted(trips, key=lambda t: t.start_ts)
        self.factors = FactorModel(kwh_per_pct, battery_usable_kwh, self.charges)
        # Energy is counted per trip from the first trip on, and on purchase before it.
        self.trips_since: datetime | None = self.trips[0].start_ts if self.trips else None
        before = [r for r in self.refuels if self.trips_since is None or r.ts < self.trips_since]
        self.trip_costs = cost_trips(
            self.trips, self.charges, self.refuels, self.factors, default_kwh_price,
            before[-1].total / before[-1].litres if before else default_l_price,
        )

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
        since = self.trips_since
        for refuel in self.refuels:
            if start_ts <= refuel.ts < end_ts:
                totals.refuel_count += 1
                if since is None or refuel.ts < since:
                    totals.fuel_l += refuel.litres
                    totals.fuel_cost += refuel.total
                    totals.purchase_energy_cost += refuel.total
        for charge in self.charges:
            if start_ts <= charge.start_ts < end_ts:
                totals.charge_count += 1
                if since is None or charge.start_ts < since:
                    totals.electricity_kwh += charge.energy_kwh
                    totals.electricity_cost += charge.cost
                    totals.purchase_energy_cost += charge.cost
        for trip in self.trips:
            if start_ts <= trip.start_ts < end_ts:
                self._add_trip(totals, trip)
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

    def _add_trip(self, totals: PeriodTotals, trip: TripData) -> None:
        cost = self.trip_costs[trip.id]
        totals.electricity_kwh += max(cost.energy_kwh, 0)
        totals.electricity_cost += cost.electricity_cost
        totals.fuel_l += cost.fuel_l
        totals.fuel_cost += cost.fuel_cost
        if trip.idle:
            totals.idle_kwh += cost.energy_kwh
            totals.idle_fuel_l += cost.fuel_l
            totals.idle_cost += cost.cost
            return
        totals.trip_count += 1
        totals.trip_km += trip.distance_km
        totals.trip_kwh += cost.energy_kwh
        totals.trip_fuel_l += cost.fuel_l
        totals.trip_cost += cost.cost
        if trip.distance_km > 0 and cost.fuel_l / trip.distance_km < ELECTRIC_L_PER_KM:
            totals.electric_km += trip.distance_km

    @property
    def last_trip(self) -> TripData | None:
        driven = [t for t in self.trips if not t.idle]
        return driven[-1] if driven else None

    def rolling_12_months(self) -> PeriodTotals:
        """The last 12 months up to and including today."""
        end = self.today + timedelta(days=1)
        return self.period(minus_year(end), end)


def minus_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)
