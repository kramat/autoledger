"""Maintenance schedules, and when each one is due (docs/api.md#resources)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book
from ..db import get_db
from ..schedules import car_service, schedules_due
from .crud import ResourceSpec, crud_router

router = APIRouter(prefix="/maintenance-schedules", tags=["maintenance-schedules"])


def _add_due(db: Session, request: Request, items: list[schemas.ScheduleOut]) -> None:
    tz = request.app.state.config.tz
    states: dict = {}
    for vehicle_id in {item.vehicle_id for item in items}:
        vehicle = db.get(models.Vehicle, vehicle_id)
        if vehicle is not None:
            book = load_book(db, vehicle, tz)
            states.update(
                {s.id: d.as_dict() for s, d in schedules_due(db, vehicle, book, active_only=False)}
            )
    for item in items:
        item.due = states.get(item.id)


SCHEDULES = ResourceSpec(
    prefix="/maintenance-schedules",
    tag="maintenance-schedules",
    model=models.MaintenanceSchedule,
    schema_in=schemas.ScheduleIn,
    schema_out=schemas.ScheduleOut,
    order_by=(models.MaintenanceSchedule.created_at,),
    decorate_items=_add_due,
)


def vehicle_due(db: Session, vehicle: models.Vehicle, book) -> dict:
    """Due state of a vehicle's active schedules, plus the car's own countdown."""
    latest = book.latest_odometer
    rate = book.km_per_day()
    return {
        "vehicle_id": vehicle.id,
        "vehicle_name": vehicle.name,
        "odometer_km": round(latest.km) if latest else None,
        "km_per_day": round(rate, 1) if rate is not None else None,
        "car_service": car_service(db, vehicle.id, book.tz),
        "items": [
            {**d.as_dict(), "category": s.category, "interval_months": s.interval_months,
             "interval_km": s.interval_km}
            for s, d in schedules_due(db, vehicle, book)
        ],
    }


@router.get("/due")
def due(request: Request, db: Session = Depends(get_db), vehicle_id: str | None = None):
    """Next due per active schedule, grouped by vehicle, most urgent first."""
    tz = request.app.state.config.tz
    stmt = select(models.Vehicle).where(models.Vehicle.deleted_at.is_(None))
    if vehicle_id:
        stmt = stmt.where(models.Vehicle.id == vehicle_id)
    else:
        stmt = stmt.where(models.Vehicle.archived_at.is_(None))
    vehicles = db.scalars(stmt.order_by(models.Vehicle.created_at)).all()
    if vehicle_id and not vehicles:
        raise HTTPException(404, f"vehicle {vehicle_id} not found")
    return {"vehicles": [vehicle_due(db, v, load_book(db, v, tz)) for v in vehicles]}


# /due goes first, so it is not taken for a schedule id.
ROUTERS = (router, crud_router(SCHEDULES))
