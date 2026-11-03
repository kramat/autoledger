"""Load a vehicle's records from the database into a ledger ``VehicleBook``."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ledger import ChargeData, ExpenseData, MaintenanceData, OdometerData, RefuelData, TripData, VehicleBook
from .models import ChargeSession, Expense, IdleRecord, MaintenanceRecord, OdometerReading, Refuel, Trip, Vehicle
from .settings_store import get_settings


def today_local(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def _active(db: Session, model, vehicle_id: str):
    return db.scalars(
        select(model).where(model.vehicle_id == vehicle_id, model.deleted_at.is_(None))
    ).all()


def _energy_override(record) -> float | None:
    return record.energy_kwh if "energy_kwh" in (record.locked_fields or []) or record.source == "manual" else None


def trip_data(trip: Trip) -> TripData:
    return TripData(
        id=trip.id,
        start_ts=trip.start_ts,
        end_ts=trip.end_ts,
        distance_km=trip.distance_km,
        battery_start_pct=trip.battery_start_pct,
        battery_used_pct=trip.battery_used_pct,
        charged_kwh=trip.charged_kwh or 0.0,
        energy_kwh=_energy_override(trip),
        fuel_start_l=trip.fuel_start_l,
        fuel_l=trip.fuel_l,
        fuel_locked="fuel_l" in (trip.locked_fields or []) or trip.source == "manual",
    )


def idle_data(idle: IdleRecord) -> TripData:
    return TripData(
        id=idle.id,
        start_ts=idle.start_ts,
        end_ts=idle.end_ts,
        battery_start_pct=idle.battery_start_pct,
        battery_used_pct=idle.battery_used_pct,
        energy_kwh=_energy_override(idle),
        fuel_l=idle.fuel_l,
        idle=True,
    )


def load_book(db: Session, vehicle: Vehicle, tz: ZoneInfo, today: date | None = None) -> VehicleBook:
    settings = get_settings(db)
    fuel = vehicle.fuel_type if vehicle.fuel_type in ("petrol", "diesel", "lpg") else "petrol"
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
            ChargeData(c.start_ts, c.energy_kwh, c.cost, c.id, c.end_ts, c.kind, c.soc_start, c.soc_end)
            for c in _active(db, ChargeSession, vehicle.id)
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
        trips=[trip_data(t) for t in _active(db, Trip, vehicle.id)]
        + [idle_data(i) for i in _active(db, IdleRecord, vehicle.id)],
        kwh_per_pct=vehicle.kwh_per_pct,
        battery_usable_kwh=vehicle.battery_usable_kwh,
        default_kwh_price=settings.electricity_price,
        default_l_price=getattr(settings.fuel_prices, fuel),
    )
