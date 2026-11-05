"""Load a vehicle's records from the database into a ledger ``VehicleBook``."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from .ledger import (
    ChargeData, DepreciationData, ExpenseData, MaintenanceData, OdometerData, OdoPoint, RefuelData, TripData,
    VehicleBook, distance_between, expense_months, local_midnight, odometer_points, split_shares,
)
from .models import ChargeSession, Expense, IdleRecord, MaintenanceRecord, OdometerReading, Refuel, Trip, Vehicle
from .settings_store import get_settings


def today_local(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def vehicle_clause(model, vehicle_id: str):
    """Records of the vehicle, including the shared expenses it takes part in."""
    clause = model.vehicle_id == vehicle_id
    if hasattr(model, "split_vehicles") and re.fullmatch(r"[\w-]+", vehicle_id):
        clause = or_(clause, cast(model.split_vehicles, String).like(f'%"{vehicle_id}"%'))
    return clause


def _active(db: Session, model, vehicle_id: str):
    return db.scalars(
        select(model).where(vehicle_clause(model, vehicle_id), model.deleted_at.is_(None))
    ).all()


class _Distances:
    """km each vehicle drove between two dates, for costs shared by km."""

    def __init__(self, db: Session, tz: ZoneInfo) -> None:
        self.db, self.tz = db, tz
        self.points: dict[str, list[OdoPoint]] = {}

    def __call__(self, vehicle_id: str, start: date, end: date) -> float:
        if vehicle_id not in self.points:
            vehicle = self.db.get(Vehicle, vehicle_id)
            self.points[vehicle_id] = odometer_points(
                self.tz, vehicle.start_date, vehicle.start_odometer_km,
                [OdometerData(r.ts, r.odometer_km) for r in _active(self.db, OdometerReading, vehicle_id)],
                [RefuelData(r.id, r.ts, r.litres, r.total, r.full_tank, r.odometer_km)
                 for r in _active(self.db, Refuel, vehicle_id)],
                [MaintenanceData(m.date, m.cost, m.odometer_km) for m in _active(self.db, MaintenanceRecord, vehicle_id)],
            )[0]
        return distance_between(self.points[vehicle_id], local_midnight(start, self.tz), local_midnight(end, self.tz))


def expense_data(db: Session, expense: Expense, vehicle_id: str, tz: ZoneInfo, today: date,
                 distances: "_Distances | None" = None) -> ExpenseData:
    """An expense as it counts for ``vehicle_id``: in full, or its share of a shared cost."""
    data = ExpenseData(expense.date, expense.amount, expense.recurrence, expense.end_date)
    if expense.split is None:
        return data
    members: dict[str, tuple[date, date | None]] = {}
    for share in expense.split_vehicles or []:
        vehicle = db.get(Vehicle, share["vehicle_id"])
        if vehicle is not None and vehicle.deleted_at is None:
            archived = vehicle.archived_at.astimezone(tz).date() if vehicle.archived_at else None
            members[vehicle.id] = (vehicle.start_date, archived)
    shares = split_shares(
        expense.split, expense_months(data, today), vehicle_id, members,
        percents={s["vehicle_id"]: s.get("percent") or 0.0 for s in expense.split_vehicles or []},
        km=distances or _Distances(db, tz),
    )
    return ExpenseData(data.date, data.amount, data.recurrence, data.end_date, shares)


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
        fuel_end_l=trip.fuel_end_l,
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
        # Tank levels are kept in auto_values (from 0.3.1 on); without them the measured drop is used.
        fuel_start_l=(idle.auto_values or {}).get("fuel_start_l"),
        fuel_end_l=(idle.auto_values or {}).get("fuel_end_l"),
        fuel_l=idle.fuel_l,
        fuel_locked="fuel_l" in (idle.locked_fields or []) or idle.source == "manual",
        idle=True,
    )


def depreciation_data(vehicle: Vehicle) -> DepreciationData | None:
    """The vehicle's depreciation, when it is switched on and complete."""
    if not vehicle.depreciation_enabled or vehicle.purchase_price is None:
        return None
    if vehicle.purchase_date is None or vehicle.resale_date is None or vehicle.resale_date <= vehicle.purchase_date:
        return None
    return DepreciationData(
        vehicle.purchase_date, vehicle.resale_date, max(vehicle.purchase_price - (vehicle.resale_estimate or 0), 0),
        count_from=vehicle.start_date,
    )


def load_book(db: Session, vehicle: Vehicle, tz: ZoneInfo, today: date | None = None) -> VehicleBook:
    settings = get_settings(db)
    fuel = vehicle.fuel_type if vehicle.fuel_type in ("petrol", "diesel", "lpg") else "petrol"
    today = today or today_local(tz)
    distances = _Distances(db, tz)
    return VehicleBook(
        tz=tz,
        today=today,
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
        expenses=[expense_data(db, e, vehicle.id, tz, today, distances) for e in _active(db, Expense, vehicle.id)],
        trips=[trip_data(t) for t in _active(db, Trip, vehicle.id)]
        + [idle_data(i) for i in _active(db, IdleRecord, vehicle.id)],
        depreciation=depreciation_data(vehicle),
        kwh_per_pct=vehicle.kwh_per_pct,
        battery_usable_kwh=vehicle.battery_usable_kwh,
        default_kwh_price=settings.electricity_price,
        default_l_price=getattr(settings.fuel_prices, fuel),
    )
