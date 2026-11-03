"""When maintenance is due. Pure functions, no database access.

The rules are documented in docs/addon.md#maintenance.
"""

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

# A km-based due date is only estimated from a driving rate of at least this much.
MIN_KM_PER_DAY = 0.5


@dataclass(frozen=True)
class ScheduleData:
    id: str
    name: str
    category: str | None = None
    interval_months: int | None = None
    interval_km: float | None = None
    last_done_date: date | None = None
    last_done_km: float | None = None
    remind_before_days: int = 30
    remind_before_km: float = 1000


@dataclass(frozen=True)
class DoneData:
    """A maintenance record, with its odometer estimated when it was not entered."""

    id: str
    date: date
    category: str
    schedule_id: str | None = None
    odometer_km: float | None = None


@dataclass(frozen=True)
class Due:
    schedule_id: str
    name: str
    status: str  # ok | soon | overdue | unknown
    last_done_date: date | None = None
    last_done_km: float | None = None
    last_record_id: str | None = None
    due_date: date | None = None
    due_km: float | None = None
    km_left: float | None = None
    # The earlier of the due date and the date the due km is expected, and what it comes from.
    estimated_date: date | None = None
    reason: str | None = None  # date | km
    days_left: int | None = None

    def as_dict(self) -> dict:
        def r(value: float | None) -> float | None:
            return None if value is None else round(value)

        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "status": self.status,
            "last_done_date": self.last_done_date,
            "last_done_km": r(self.last_done_km),
            "last_record_id": self.last_record_id,
            "due_date": self.due_date,
            "due_km": r(self.due_km),
            "km_left": r(self.km_left),
            "estimated_date": self.estimated_date,
            "reason": self.reason,
            "days_left": self.days_left,
        }


STATUS_ORDER = {"overdue": 0, "soon": 1, "ok": 2, "unknown": 3}


def add_months_exact(day: date, months: int) -> date:
    """The same day ``months`` later, or the last day of a shorter month."""
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def fulfils(record: DoneData, schedule: ScheduleData) -> bool:
    """A linked record fulfils its schedule; an unlinked one every schedule of its category."""
    if record.schedule_id is not None:
        return record.schedule_id == schedule.id
    return schedule.category is not None and record.category == schedule.category


def last_done(schedule: ScheduleData, records: Iterable[DoneData]) -> tuple[date | None, float | None, str | None]:
    """The latest of the schedule's starting point and the records that fulfil it."""
    done_date, done_km, record_id = schedule.last_done_date, schedule.last_done_km, None
    for record in sorted((r for r in records if fulfils(r, schedule)), key=lambda r: r.date):
        if done_date is None or record.date >= done_date:
            done_date, done_km, record_id = record.date, record.odometer_km, record.id
    return done_date, done_km, record_id


def due(
    schedule: ScheduleData,
    records: Iterable[DoneData],
    today: date,
    odometer_km: float | None = None,
    odometer_date: date | None = None,
    km_per_day: float | None = None,
) -> Due:
    """Next due date and km of one schedule.

    ``odometer_km`` is the latest known odometer, read on ``odometer_date``. The
    date at which the due km is reached is estimated from there at ``km_per_day``.
    """
    done_date, done_km, record_id = last_done(schedule, records)
    due_date = (
        add_months_exact(done_date, schedule.interval_months)
        if done_date is not None and schedule.interval_months
        else None
    )
    due_km = done_km + schedule.interval_km if done_km is not None and schedule.interval_km else None
    km_left = due_km - odometer_km if due_km is not None and odometer_km is not None else None

    km_date = None
    if km_left is not None and km_per_day is not None and km_per_day >= MIN_KM_PER_DAY:
        km_date = (odometer_date or today) + timedelta(days=max(km_left, 0) / km_per_day)

    candidates = [(d, reason) for d, reason in ((due_date, "date"), (km_date, "km")) if d is not None]
    estimated_date, reason = min(candidates) if candidates else (None, None)
    if reason is None and km_left is not None:
        reason = "km"
    days_left = (estimated_date - today).days if estimated_date is not None else None

    if due_date is None and km_left is None:
        status = "unknown"
    elif (due_date is not None and today > due_date) or (km_left is not None and km_left <= 0):
        status = "overdue"
    elif (
        (days_left is not None and days_left <= schedule.remind_before_days)
        or (km_left is not None and km_left <= schedule.remind_before_km)
    ):
        status = "soon"
    else:
        status = "ok"

    return Due(
        schedule_id=schedule.id,
        name=schedule.name,
        status=status,
        last_done_date=done_date,
        last_done_km=done_km,
        last_record_id=record_id,
        due_date=due_date,
        due_km=due_km,
        km_left=km_left,
        estimated_date=estimated_date,
        reason=reason,
        days_left=days_left,
    )


def next_due(items: Iterable[Due]) -> Due | None:
    """The schedule that needs attention first: by status, then by date."""
    known = [d for d in items if d.status != "unknown"]
    if not known:
        return None
    return min(known, key=lambda d: (STATUS_ORDER[d.status], d.estimated_date or date.max, d.km_left or 0))
