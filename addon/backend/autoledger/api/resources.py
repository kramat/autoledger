"""Routers for vehicles, refuels, odometer readings, maintenance and expenses."""

from fastapi import Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book
from ..db import utcnow
from .crud import crud_router, field_error


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


vehicles = crud_router(
    prefix="/vehicles",
    tag="vehicles",
    model=models.Vehicle,
    schema_in=schemas.VehicleIn,
    schema_out=schemas.VehicleOut,
    order_by=(models.Vehicle.created_at,),
    prepare_patch=_vehicle_patch,
)

refuels = crud_router(
    prefix="/refuels",
    tag="refuels",
    model=models.Refuel,
    schema_in=schemas.RefuelIn,
    schema_out=schemas.RefuelOut,
    order_by=(models.Refuel.ts.desc(),),
    time_field="ts",
    prepare_patch=_refuel_patch,
    decorate_items=_add_consumption,
)

odometer_readings = crud_router(
    prefix="/odometer-readings",
    tag="odometer-readings",
    model=models.OdometerReading,
    schema_in=schemas.OdometerIn,
    schema_out=schemas.OdometerOut,
    order_by=(models.OdometerReading.ts.desc(),),
    time_field="ts",
)

maintenance = crud_router(
    prefix="/maintenance",
    tag="maintenance",
    model=models.MaintenanceRecord,
    schema_in=schemas.MaintenanceIn,
    schema_out=schemas.MaintenanceOut,
    order_by=(models.MaintenanceRecord.date.desc(), models.MaintenanceRecord.created_at.desc()),
    time_field="date",
)

expenses = crud_router(
    prefix="/expenses",
    tag="expenses",
    model=models.Expense,
    schema_in=schemas.ExpenseIn,
    schema_out=schemas.ExpenseOut,
    order_by=(models.Expense.date.desc(), models.Expense.created_at.desc()),
    time_field="date",
)

ROUTERS = (vehicles, refuels, odometer_readings, maintenance, expenses)
