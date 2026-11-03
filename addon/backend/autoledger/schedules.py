"""Maintenance schedules of a vehicle with their due state, and the car's own service countdown."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ledger import VehicleBook, local_noon, odometer_at
from .maintenance import STATUS_ORDER, DoneData, Due, ScheduleData, due
from .models import MaintenanceRecord, MaintenanceSchedule, Setting, Vehicle
from .schemas import CarServiceOut, ServiceStatusPayload

_CAR_SERVICE_KEY = "car_service:{}"


def save_car_service(db: Session, vehicle_id: str, data: ServiceStatusPayload, reported_at: datetime) -> None:
    key = _CAR_SERVICE_KEY.format(vehicle_id)
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key)
        db.add(row)
    row.value = {**data.model_dump(), "reported_at": reported_at.isoformat()}


def car_service(db: Session, vehicle_id: str, tz: ZoneInfo) -> CarServiceOut | None:
    row = db.get(Setting, _CAR_SERVICE_KEY.format(vehicle_id))
    if row is None or not isinstance(row.value, dict):
        return None
    result = CarServiceOut.model_validate(row.value)
    if result.days_to_service is not None:
        result.due_date = result.reported_at.astimezone(tz).date() + timedelta(days=round(result.days_to_service))
    if result.distance_to_service is not None and result.odometer_km is not None:
        result.due_km = round(result.odometer_km + result.distance_to_service)
    return result


def schedule_data(schedule: MaintenanceSchedule) -> ScheduleData:
    return ScheduleData(
        id=schedule.id,
        name=schedule.name,
        category=schedule.category,
        interval_months=schedule.interval_months,
        interval_km=schedule.interval_km,
        last_done_date=schedule.last_done_date,
        last_done_km=schedule.last_done_km,
        remind_before_days=schedule.remind_before_days,
        remind_before_km=schedule.remind_before_km,
    )


def schedules_due(
    db: Session, vehicle: Vehicle, book: VehicleBook, *, active_only: bool = True
) -> list[tuple[MaintenanceSchedule, Due]]:
    """Every schedule of the vehicle with its due state, in the order they need attention."""
    stmt = select(MaintenanceSchedule).where(
        MaintenanceSchedule.vehicle_id == vehicle.id, MaintenanceSchedule.deleted_at.is_(None)
    )
    if active_only:
        stmt = stmt.where(MaintenanceSchedule.active.is_(True))
    schedules = db.scalars(stmt).all()
    if not schedules:
        return []

    records = [
        DoneData(
            id=m.id,
            date=m.date,
            category=m.category,
            schedule_id=m.schedule_id,
            # Without an odometer value, the km-based interval counts from the estimated value.
            odometer_km=m.odometer_km if m.odometer_km is not None
            else odometer_at(book.points, local_noon(m.date, book.tz)),
        )
        for m in db.scalars(
            select(MaintenanceRecord).where(
                MaintenanceRecord.vehicle_id == vehicle.id, MaintenanceRecord.deleted_at.is_(None)
            )
        )
    ]
    latest = book.latest_odometer
    rate = book.km_per_day()
    result = [
        (
            schedule,
            due(
                schedule_data(schedule),
                records,
                book.today,
                odometer_km=latest.km if latest else None,
                odometer_date=latest.ts.astimezone(book.tz).date() if latest else None,
                km_per_day=rate,
            ),
        )
        for schedule in schedules
    ]
    result.sort(key=lambda pair: (STATUS_ORDER[pair[1].status], pair[1].estimated_date or date.max))
    return result
