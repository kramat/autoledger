"""Load a vehicle's records from the database into a ledger ``VehicleBook``."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ledger import ChargeData, ExpenseData, MaintenanceData, OdometerData, RefuelData, VehicleBook
from .models import ChargeSession, Expense, MaintenanceRecord, OdometerReading, Refuel, Vehicle


def today_local(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def _active(db: Session, model, vehicle_id: str):
    return db.scalars(
        select(model).where(model.vehicle_id == vehicle_id, model.deleted_at.is_(None))
    ).all()


def load_book(db: Session, vehicle: Vehicle, tz: ZoneInfo, today: date | None = None) -> VehicleBook:
    return VehicleBook(
        tz=tz,
        today=today or today_local(tz),
        start_date=vehicle.start_date,
        start_odometer_km=vehicle.start_odometer_km,
        refuels=[
            RefuelData(r.id, r.ts, r.litres, r.total, r.full_tank, r.odometer_km)
            for r in _active(db, Refuel, vehicle.id)
        ],
        charges=[
            ChargeData(c.start_ts, c.energy_kwh, c.cost) for c in _active(db, ChargeSession, vehicle.id)
        ],
        readings=[OdometerData(r.ts, r.odometer_km) for r in _active(db, OdometerReading, vehicle.id)],
        maintenance=[
            MaintenanceData(m.date, m.cost, m.odometer_km)
            for m in _active(db, MaintenanceRecord, vehicle.id)
        ],
        expenses=[
            ExpenseData(e.date, e.amount, e.recurrence, e.end_date)
            for e in _active(db, Expense, vehicle.id)
        ],
    )
