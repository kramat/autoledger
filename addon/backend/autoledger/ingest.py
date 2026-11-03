"""Apply collector events (docs/api.md#ingest-collector--add-on-m2).

Every event is applied at most once (by uuid) inside its own savepoint, so one
bad event never blocks the rest of a batch. Rejected events are logged and
create a review item; nothing is dropped silently.
"""

import logging
from collections.abc import Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .charging import update_cost
from .db import utcnow
from .models import ChargeSession, IdleRecord, IngestEvent, OdometerReading, Refuel, Trip, Vehicle
from .review import add_item
from .schedules import save_car_service
from .schemas import (
    ChargePayload,
    ExternalChargePayload,
    IdlePayload,
    IngestEventIn,
    OdometerPayload,
    RefuelPayload,
    ServiceStatusPayload,
    SettingsModel,
    SocUpdatePayload,
    TripPayload,
)

_LOGGER = logging.getLogger(__name__)


class IngestError(Exception):
    pass


def _set(obj, field: str, value) -> None:
    """Set a field unless the user edited it (locked)."""
    if field not in (obj.locked_fields or []):
        setattr(obj, field, value)


def _vehicle(db: Session, event: IngestEventIn, required: bool = True) -> Vehicle | None:
    if event.vehicle_id is None:
        if required:
            raise IngestError("vehicle_id is required for this event")
        return None
    vehicle = db.get(Vehicle, event.vehicle_id)
    if vehicle is None or vehicle.deleted_at is not None:
        raise IngestError(f"Unknown vehicle {event.vehicle_id}")
    return vehicle


def _payload[T: BaseModel](model: type[T], event: IngestEventIn) -> T:
    try:
        return model.model_validate(event.payload)
    except ValidationError as err:
        raise IngestError(f"Invalid payload: {err.errors(include_url=False)}") from err


# --- Handlers -------------------------------------------------------------


def _charge(db: Session, event: IngestEventIn, _settings: SettingsModel) -> str:
    data = _payload(ChargePayload, event)
    vehicle = _vehicle(db, event, required=False)
    completed = event.type == "charge.completed"

    session = db.scalars(select(ChargeSession).where(ChargeSession.session_key == data.session_id)).first()
    if session is None:
        session = ChargeSession(
            session_key=data.session_id,
            kind="home",
            source="collector",
            price_mode="samples",
            start_ts=data.start_ts,
            is_open=True,
            locked_fields=[],
            auto_values={},
        )
        db.add(session)
    elif not session.is_open and not completed:
        return session.id  # a late progress event for a finished session

    _set(session, "vehicle_id", session.vehicle_id or (vehicle.id if vehicle else None))
    session.charger_key = data.charger_key or session.charger_key
    session.charger_name = data.charger_name or session.charger_name
    _set(session, "start_ts", min(session.start_ts, data.start_ts))
    _set(session, "end_ts", data.end_ts)
    _set(session, "energy_kwh", round(data.energy_kwh, 4))
    if data.cost is not None:
        session.auto_cost = round(data.cost, 4)
    if data.price_samples is not None:
        session.price_samples = [s.model_dump(mode="json") for s in data.price_samples]
    if data.soc_start is not None:
        _set(session, "soc_start", data.soc_start)
    if data.soc_end is not None:
        _set(session, "soc_end", data.soc_end)
    session.is_open = not completed
    update_cost(db, session)
    db.flush()

    if completed and session.vehicle_id is None:
        add_item(
            db,
            "charge_without_vehicle",
            record_type="charge",
            record_id=session.id,
            details={"energy_kwh": session.energy_kwh, "charger": session.charger_name},
        )
    return session.id


def _soc_update(db: Session, event: IngestEventIn, _settings: SettingsModel) -> str | None:
    data = _payload(SocUpdatePayload, event)
    session = db.scalars(select(ChargeSession).where(ChargeSession.session_key == data.session_id)).first()
    if session is None:
        return None
    if data.soc_start is not None:
        _set(session, "soc_start", data.soc_start)
    if data.soc_end is not None:
        _set(session, "soc_end", data.soc_end)
    return session.id


def _external_charge(db: Session, event: IngestEventIn, settings: SettingsModel) -> str:
    data = _payload(ExternalChargePayload, event)
    vehicle = _vehicle(db, event)
    session = ChargeSession(
        vehicle_id=vehicle.id,
        session_key=f"ext-{event.uuid}",
        kind="public",
        source="collector",
        status="needs_review",
        start_ts=data.window_start,
        end_ts=data.window_end,
        is_open=False,
        lat=data.place.lat,
        lon=data.place.lon,
        address=data.place.address,
        energy_kwh=round(data.energy_kwh_estimated, 3),
        energy_estimated=True,
        soc_start=data.battery_start_pct,
        soc_end=data.battery_end_pct,
        price_mode="per_kwh",
        price_per_kwh=settings.public_charge_price,
        locked_fields=[],
        auto_values={},
    )
    update_cost(db, session)
    db.add(session)
    db.flush()
    reason = "possible_engine_charge" if "possible_engine_charge" in data.flags else "public_charge_price"
    add_item(
        db,
        reason,
        vehicle_id=vehicle.id,
        record_type="charge",
        record_id=session.id,
        details={
            "energy_kwh": session.energy_kwh,
            "battery": [data.battery_start_pct, data.battery_end_pct],
            "car_reported_charging": data.car_reported_charging,
            "flags": data.flags,
        },
    )
    return session.id


def _refuel(db: Session, event: IngestEventIn, settings: SettingsModel) -> str:
    data = _payload(RefuelPayload, event)
    vehicle = _vehicle(db, event)

    price, source = data.suggested_price_per_l, data.price_source
    if price is None:
        last = db.scalars(
            select(Refuel)
            .where(Refuel.vehicle_id == vehicle.id, Refuel.deleted_at.is_(None), Refuel.ts < data.ts)
            .order_by(Refuel.ts.desc())
            .limit(1)
        ).first()
        if last is not None:
            price, source = last.price_per_l, "last_refuel"
        else:
            fuel = vehicle.fuel_type if vehicle.fuel_type in ("petrol", "diesel", "lpg") else "petrol"
            price, source = getattr(settings.fuel_prices, fuel), "default"

    litres = round(data.litres_estimated, 2)
    full = vehicle.tank_l is None or data.fuel_end_l >= 0.92 * vehicle.tank_l
    refuel = Refuel(
        vehicle_id=vehicle.id,
        ts=data.ts,
        odometer_km=data.odometer_km,
        litres=litres,
        price_per_l=round(price, 4),
        total=round(litres * price, 2),
        full_tank=full,
        station=data.place.address,
        source="collector",
        status="needs_review",
        locked_fields=[],
        auto_values={"price_source": source, "fuel_start_l": data.fuel_start_l, "fuel_end_l": data.fuel_end_l},
    )
    db.add(refuel)
    db.flush()
    add_item(
        db,
        "refuel_price",
        vehicle_id=vehicle.id,
        record_type="refuel",
        record_id=refuel.id,
        details={"litres": litres, "suggested_price_per_l": price, "price_source": source},
    )
    return refuel.id


def _odometer(db: Session, event: IngestEventIn, _settings: SettingsModel) -> str:
    data = _payload(OdometerPayload, event)
    vehicle = _vehicle(db, event)
    existing = db.scalars(
        select(OdometerReading).where(OdometerReading.vehicle_id == vehicle.id, OdometerReading.ts == data.ts)
    ).first()
    if existing:
        return existing.id
    reading = OdometerReading(
        vehicle_id=vehicle.id, ts=data.ts, odometer_km=data.odometer_km, source="collector", locked_fields=[],
        auto_values={},
    )
    db.add(reading)
    db.flush()
    return reading.id


def _pct_drop(start: float | None, end: float | None) -> float | None:
    return None if start is None or end is None else round(start - end, 2)


def _litres_used(start: float | None, end: float | None) -> float:
    """Provisional litres: a rise or a negative noise value counts as 0 (see docs/costs.md)."""
    return 0.0 if start is None or end is None else round(max(start - end, 0.0), 2)


def _trip(db: Session, event: IngestEventIn, _settings: SettingsModel) -> str:
    data = _payload(TripPayload, event)
    vehicle = _vehicle(db, event)
    trip = Trip(
        vehicle_id=vehicle.id,
        start_ts=data.start_ts,
        start_ts_estimated=data.start_ts_estimated,
        end_ts=data.end_ts,
        start_lat=data.start.lat,
        start_lon=data.start.lon,
        start_address=data.start.address,
        start_zone=data.start.zone,
        end_lat=data.end.lat,
        end_lon=data.end.lon,
        end_address=data.end.address,
        end_zone=data.end.zone,
        kind=data.kind,
        odometer_start=data.odometer_start,
        odometer_end=data.odometer_end,
        distance_km=round(data.distance_km, 2),
        distance_source=data.distance_source,
        battery_start_pct=data.battery_start_pct,
        battery_end_pct=data.battery_end_pct,
        battery_used_pct=_pct_drop(data.battery_start_pct, data.battery_end_pct),
        charged_kwh=round(data.charged_kwh, 3),
        fuel_start_l=data.fuel_start_l,
        fuel_end_l=data.fuel_end_l,
        fuel_l=_litres_used(data.fuel_start_l, data.fuel_end_l),
        source="collector",
        locked_fields=[],
        auto_values={"flags": data.flags} if data.flags else {},
        origin={},
    )
    db.add(trip)
    db.flush()
    return trip.id


def _idle(db: Session, event: IngestEventIn, _settings: SettingsModel) -> str:
    data = _payload(IdlePayload, event)
    vehicle = _vehicle(db, event)
    idle = IdleRecord(
        vehicle_id=vehicle.id,
        start_ts=data.start_ts,
        end_ts=data.end_ts,
        zone=data.zone,
        battery_start_pct=data.battery_start_pct,
        battery_end_pct=data.battery_end_pct,
        battery_used_pct=_pct_drop(data.battery_start_pct, data.battery_end_pct),
        fuel_l=_litres_used(data.fuel_start_l, data.fuel_end_l),
        source="collector",
        locked_fields=[],
        auto_values={"fuel_start_l": data.fuel_start_l, "fuel_end_l": data.fuel_end_l}
        if data.fuel_start_l is not None and data.fuel_end_l is not None else {},
    )
    db.add(idle)
    db.flush()
    return idle.id


def _service_status(db: Session, event: IngestEventIn, _settings: SettingsModel) -> None:
    """The car's own service countdown, shown next to the maintenance schedules."""
    vehicle = _vehicle(db, event)
    save_car_service(db, vehicle.id, _payload(ServiceStatusPayload, event), event.occurred_at)
    return None


HANDLERS: dict[str, Callable[[Session, IngestEventIn, SettingsModel], str | None]] = {
    "trip.recorded": _trip,
    "idle.recorded": _idle,
    "charge.started": _charge,
    "charge.updated": _charge,
    "charge.completed": _charge,
    "charge.soc_update": _soc_update,
    "external_charge.detected": _external_charge,
    "refuel.detected": _refuel,
    "odometer.reading": _odometer,
    "service.status": _service_status,
}


def ingest(db: Session, events: list[IngestEventIn], settings: SettingsModel) -> dict:
    accepted: list[dict] = []
    duplicates: list[str] = []
    rejected: list[dict] = []

    for event in events:
        if db.get(IngestEvent, event.uuid) is not None:
            duplicates.append(event.uuid)
            continue
        record_id, error = None, None
        try:
            handler = HANDLERS.get(event.type)
            if handler is None:
                raise IngestError(f"Unsupported event type {event.type!r}")
            with db.begin_nested():
                record_id = handler(db, event, settings)
        except IngestError as err:
            error = str(err)
            _LOGGER.warning("Rejected collector event %s (%s): %s", event.uuid, event.type, error)
            add_item(db, "rejected_event", vehicle_id=None, details={"uuid": event.uuid, "type": event.type,
                                                                       "error": error})
        db.add(
            IngestEvent(
                uuid=event.uuid,
                type=event.type,
                vehicle_id=event.vehicle_id,
                occurred_at=event.occurred_at,
                received_at=utcnow(),
                payload=event.payload,
                result="rejected" if error else "applied",
                record_id=record_id,
                error=error,
            )
        )
        if error:
            rejected.append({"uuid": event.uuid, "error": error})
        else:
            accepted.append({"uuid": event.uuid, "record_id": record_id})
    db.commit()
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}
