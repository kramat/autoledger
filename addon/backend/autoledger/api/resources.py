"""Routers for vehicles, refuels, odometer readings, charges, maintenance and expenses."""

from fastapi import Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book
from ..charging import update_cost
from ..db import utcnow
from ..review import resolve_for_record
from .crud import ResourceSpec, crud_router, field_error


def _vehicle_patch(obj: models.Vehicle, current: dict, body: dict) -> None:
    """``archived: true/false`` is accepted as a shortcut for archived_at."""
    if "archived" in body:
        archived = body.pop("archived")
        if not isinstance(archived, bool):
            raise field_error("archived", "Must be true or false")
        obj.archived_at = (obj.archived_at or utcnow()) if archived else None


def _refuel_patch(obj: models.Refuel, current: dict, body: dict) -> None:
    """Recalculate the value the user did not touch.

    Changing the total keeps litres and recalculates the price; changing the
    price keeps litres and recalculates the total; changing only the litres
    keeps the price.
    """
    touched = {"litres", "price_per_l", "total"} & body.keys()
    if not touched:
        return
    if "total" in touched and "price_per_l" not in touched:
        current["price_per_l"] = None
    elif "price_per_l" in touched and "total" not in touched:
        current["total"] = None
    elif touched == {"litres"}:
        current["total"] = None


def _confirm_when_edited(fields: set[str]):
    """An automatic record the user corrects is confirmed and leaves the review inbox."""

    def after_update(db: Session, obj, changed: list[str]) -> None:
        if obj.status != "ok" and fields & set(changed):
            obj.status = "ok"
            resolve_for_record(db, obj.id, {"action": "edited", "fields": changed})

    return after_update


def _check_schedule(db: Session, obj: models.MaintenanceRecord) -> None:
    if obj.schedule_id is None:
        return
    schedule = db.get(models.MaintenanceSchedule, obj.schedule_id)
    if schedule is None or schedule.deleted_at is not None or schedule.vehicle_id != obj.vehicle_id:
        raise field_error("schedule_id", "Pick a schedule of the same vehicle")


def _add_consumption(db: Session, request: Request, items: list[schemas.RefuelOut]) -> None:
    """Attach full-to-full consumption to the refuels that close an interval."""
    tz = request.app.state.config.tz
    intervals: dict = {}
    for vehicle_id in {item.vehicle_id for item in items}:
        vehicle = db.get(models.Vehicle, vehicle_id)
        if vehicle is not None:
            intervals.update(load_book(db, vehicle, tz).interval_by_refuel())
    for item in items:
        interval = intervals.get(item.id)
        if interval is not None:
            item.interval_km = round(interval.km, 1)
            item.l_per_100km = round(interval.l_per_100km, 2)


VEHICLES = ResourceSpec(
    prefix="/vehicles",
    tag="vehicles",
    model=models.Vehicle,
    schema_in=schemas.VehicleIn,
    schema_out=schemas.VehicleOut,
    order_by=(models.Vehicle.created_at,),
    prepare_patch=_vehicle_patch,
)

REFUELS = ResourceSpec(
    prefix="/refuels",
    tag="refuels",
    model=models.Refuel,
    schema_in=schemas.RefuelIn,
    schema_out=schemas.RefuelOut,
    order_by=(models.Refuel.ts.desc(),),
    time_field="ts",
    prepare_patch=_refuel_patch,
    after_update=_confirm_when_edited({"litres", "price_per_l", "total"}),
    decorate_items=_add_consumption,
)

ODOMETER_READINGS = ResourceSpec(
    prefix="/odometer-readings",
    tag="odometer-readings",
    model=models.OdometerReading,
    schema_in=schemas.OdometerIn,
    schema_out=schemas.OdometerOut,
    order_by=(models.OdometerReading.ts.desc(),),
    time_field="ts",
)

CHARGES = ResourceSpec(
    prefix="/charges",
    tag="charges",
    model=models.ChargeSession,
    schema_in=schemas.ChargeIn,
    schema_out=schemas.ChargeOut,
    order_by=(models.ChargeSession.start_ts.desc(),),
    time_field="start_ts",
    before_save=update_cost,
    after_update=_confirm_when_edited(
        {"vehicle_id", "energy_kwh", "price_mode", "price_per_kwh", "price_total", "session_fee"}
    ),
)

MAINTENANCE = ResourceSpec(
    prefix="/maintenance",
    tag="maintenance",
    model=models.MaintenanceRecord,
    schema_in=schemas.MaintenanceIn,
    schema_out=schemas.MaintenanceOut,
    order_by=(models.MaintenanceRecord.date.desc(), models.MaintenanceRecord.created_at.desc()),
    time_field="date",
    before_save=_check_schedule,
)

EXPENSES = ResourceSpec(
    prefix="/expenses",
    tag="expenses",
    model=models.Expense,
    schema_in=schemas.ExpenseIn,
    schema_out=schemas.ExpenseOut,
    order_by=(models.Expense.date.desc(), models.Expense.created_at.desc()),
    time_field="date",
)

# record_type used by review items -> resource
BY_RECORD_TYPE = {"refuel": REFUELS, "charge": CHARGES}

ROUTERS = tuple(
    crud_router(spec) for spec in (VEHICLES, REFUELS, ODOMETER_READINGS, CHARGES, MAINTENANCE, EXPENSES)
)
