"""Trips and idle records: CRUD with costing, plus split and merge (docs/api.md#resources)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book
from ..db import get_db, utcnow
from .crud import ResourceSpec, crud_router, field_error


def _costings(db: Session, request: Request, vehicle_ids: set[str]) -> dict[str, dict]:
    tz = request.app.state.config.tz
    result: dict[str, dict] = {}
    for vehicle_id in vehicle_ids:
        vehicle = db.get(models.Vehicle, vehicle_id)
        if vehicle is not None:
            book = load_book(db, vehicle, tz)
            result.update({key: cost.as_dict() for key, cost in book.trip_costs.items()})
    return result


def _add_costing(db: Session, request: Request, items: list) -> None:
    costs = _costings(db, request, {item.vehicle_id for item in items})
    for item in items:
        if item.id in costs:
            item.costing = schemas.TripCostOut(**costs[item.id])


def _battery_patch(obj, current: dict, body: dict) -> None:
    """Editing the battery start or end recalculates the % used, unless that is given too."""
    if {"battery_start_pct", "battery_end_pct"} & body.keys() and "battery_used_pct" not in body:
        current["battery_used_pct"] = None


TRIPS = ResourceSpec(
    prefix="/trips",
    tag="trips",
    model=models.Trip,
    schema_in=schemas.TripIn,
    schema_out=schemas.TripOut,
    order_by=(models.Trip.start_ts.desc(),),
    time_field="start_ts",
    prepare_patch=_battery_patch,
    decorate_items=_add_costing,
)

IDLE_RECORDS = ResourceSpec(
    prefix="/idle-records",
    tag="idle-records",
    model=models.IdleRecord,
    schema_in=schemas.IdleIn,
    schema_out=schemas.IdleOut,
    order_by=(models.IdleRecord.start_ts.desc(),),
    time_field="start_ts",
    prepare_patch=_battery_patch,
    decorate_items=_add_costing,
)

# The fixed paths are registered before the generic /{item_id} routes.
router = APIRouter(prefix="/trips", tags=["trips"])

_COPY = (
    "vehicle_id", "start_ts_estimated", "start_lat", "start_lon", "start_address", "start_zone",
    "end_lat", "end_lon", "end_address", "end_zone", "odometer_start", "odometer_end", "distance_source",
    "battery_start_pct", "battery_end_pct", "fuel_start_l", "fuel_end_l", "source", "note",
)


def _active_trip(db: Session, trip_id: str) -> models.Trip:
    trip = db.get(models.Trip, trip_id)
    if trip is None or trip.deleted_at is not None:
        raise HTTPException(404, f"trip {trip_id} not found")
    return trip


def _clone(trip: models.Trip, **values) -> models.Trip:
    data = {key: getattr(trip, key) for key in _COPY}
    data.update(
        locked_fields=list(trip.locked_fields or []), auto_values=dict(trip.auto_values or {}), status="ok",
        start_ts=trip.start_ts, end_ts=trip.end_ts, kind=trip.kind, energy_kwh=trip.energy_kwh,
    )
    data.update(values)
    return models.Trip(**data)


def _scaled(value: float | None, fraction: float) -> float | None:
    return None if value is None else round(value * fraction, 3)


def _out(db: Session, request: Request, trips: list[models.Trip]) -> list[schemas.TripOut]:
    items = [schemas.TripOut.model_validate(t) for t in trips]
    _add_costing(db, request, items)
    return items


@router.post("/merge", response_model=schemas.TripOut, name="merge_trips")
def merge_trips(body: schemas.MergeIn, request: Request, db: Session = Depends(get_db)):
    a, b = sorted((_active_trip(db, i) for i in body.ids), key=lambda t: t.start_ts)
    if a.id == b.id or a.vehicle_id != b.vehicle_id:
        raise field_error("ids", "Choose two different trips of the same vehicle")
    between = db.scalars(
        select(models.Trip).where(
            models.Trip.vehicle_id == a.vehicle_id, models.Trip.deleted_at.is_(None),
            models.Trip.id.notin_((a.id, b.id)),
            models.Trip.start_ts >= a.start_ts, models.Trip.start_ts <= b.start_ts,
        )
    ).first()
    if between is not None:
        raise field_error("ids", "Only adjacent trips can be merged")

    def total(field: str) -> float | None:
        values = [getattr(t, field) for t in (a, b) if getattr(t, field) is not None]
        return round(sum(values), 3) if values else None

    locked = sorted(set(a.locked_fields or []) | set(b.locked_fields or []))
    energy = None
    if "energy_kwh" in locked or a.source == "manual" or b.source == "manual":
        # A value set by hand on either part is kept: the merged trip gets the sum of both costed values.
        costs = _costings(db, request, {a.vehicle_id})
        energy = round(sum(costs[t.id]["energy_kwh"] for t in (a, b)), 3)
        locked = sorted(set(locked) | {"energy_kwh"})
    same_place = a.start_zone is not None and a.start_zone == b.end_zone
    merged = _clone(
        a,
        end_ts=b.end_ts, end_lat=b.end_lat, end_lon=b.end_lon, end_address=b.end_address, end_zone=b.end_zone,
        odometer_end=b.odometer_end, battery_end_pct=b.battery_end_pct, fuel_end_l=b.fuel_end_l,
        distance_km=round(a.distance_km + b.distance_km, 2),
        battery_used_pct=total("battery_used_pct"), charged_kwh=round((a.charged_kwh or 0) + (b.charged_kwh or 0), 3),
        fuel_l=round(a.fuel_l + b.fuel_l, 2), energy_kwh=energy, locked_fields=locked,
        kind="round_trip" if same_place else "one_way",
        note="\n".join(n for n in (a.note, b.note) if n) or None,
        origin={"merged_from": [a.id, b.id]},
    )
    now = utcnow()
    for trip in (a, b):
        trip.deleted_at, trip.version = now, trip.version + 1
    db.add(merged)
    db.commit()
    db.refresh(merged)
    return _out(db, request, [merged])[0]


@router.post("/{trip_id}/split", response_model=list[schemas.TripOut], name="split_trip")
def split_trip(trip_id: str, body: schemas.SplitIn, request: Request, db: Session = Depends(get_db)):
    trip = _active_trip(db, trip_id)
    if not 0 < body.at_km < trip.distance_km:
        raise field_error("at_km", f"Must be between 0 and {trip.distance_km:g} km")
    if not trip.start_ts < body.at_ts < trip.end_ts:
        raise field_error("at_ts", "Must be between the start and the end of the trip")
    first = body.at_km / trip.distance_km
    second = 1 - first
    stop = {"address": body.address, "odometer": None if trip.odometer_start is None
            else round(trip.odometer_start + body.at_km, 1)}
    origin = {"split_from": trip.id}
    part_a = _clone(
        trip, end_ts=body.at_ts, end_lat=None, end_lon=None, end_address=stop["address"], end_zone=None,
        odometer_end=stop["odometer"], battery_end_pct=None, fuel_end_l=None, distance_km=round(body.at_km, 2),
        battery_used_pct=_scaled(trip.battery_used_pct, first), charged_kwh=_scaled(trip.charged_kwh, first) or 0,
        fuel_l=round(trip.fuel_l * first, 2), energy_kwh=_scaled(trip.energy_kwh, first), kind="one_way",
        origin=origin,
    )
    part_b = _clone(
        trip, start_ts=body.at_ts, start_ts_estimated=False, start_lat=None, start_lon=None,
        start_address=stop["address"], start_zone=None, odometer_start=stop["odometer"], battery_start_pct=None,
        fuel_start_l=None, distance_km=round(trip.distance_km - body.at_km, 2),
        battery_used_pct=_scaled(trip.battery_used_pct, second), charged_kwh=_scaled(trip.charged_kwh, second) or 0,
        fuel_l=round(trip.fuel_l * second, 2), energy_kwh=_scaled(trip.energy_kwh, second), kind="one_way",
        note=None, origin=origin,
    )
    trip.deleted_at, trip.version = utcnow(), trip.version + 1
    db.add_all([part_a, part_b])
    db.commit()
    db.refresh(part_a)
    db.refresh(part_b)
    return _out(db, request, [part_a, part_b])


ROUTERS = (router, crud_router(TRIPS), crud_router(IDLE_RECORDS))
