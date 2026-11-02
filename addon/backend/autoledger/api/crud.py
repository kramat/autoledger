"""Generic list / get / create / patch / delete / restore routes for a resource.

PATCH bodies are merged onto the stored record and the result is validated with
the full input model, so cross-field rules (such as refuel litres × price =
total) always hold.
"""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import UTCDateTime, get_db, utcnow
from ..ledger import local_midnight
from ..models import Vehicle
from ..schemas import Page

PreparePatch = Callable[[Any, dict, dict], None]
DecorateItems = Callable[[Session, Request, list], None]


def field_error(field: str, message: str) -> RequestValidationError:
    return RequestValidationError([{"loc": ("body", field), "msg": message, "type": "value_error"}])


def check_vehicle(db: Session, data: dict) -> None:
    vehicle_id = data.get("vehicle_id")
    if vehicle_id is None:
        return
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.deleted_at is not None:
        raise field_error("vehicle_id", "Unknown vehicle")


def filtered_query(model, time_field: str | None, request: Request, vehicle_id, from_, to, include_deleted):
    stmt = select(model)
    if not include_deleted:
        stmt = stmt.where(model.deleted_at.is_(None))
    if vehicle_id and hasattr(model, "vehicle_id"):
        stmt = stmt.where(model.vehicle_id == vehicle_id)
    if time_field:
        column = getattr(model, time_field)
        tz = request.app.state.config.tz

        def bound(day: date):
            return local_midnight(day, tz) if isinstance(column.type, UTCDateTime) else day

        if from_:
            stmt = stmt.where(column >= bound(from_))
        if to:
            stmt = stmt.where(column < bound(to + timedelta(days=1)))
    return stmt


def crud_router(
    *,
    prefix: str,
    tag: str,
    model,
    schema_in: type[BaseModel],
    schema_out: type[BaseModel],
    order_by: tuple,
    time_field: str | None = None,
    prepare_patch: PreparePatch | None = None,
    decorate_items: DecorateItems | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    def get_or_404(db: Session, item_id: str):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(404, f"{tag} {item_id} not found")
        return obj

    @router.get("", response_model=Page[schema_out], name=f"list_{tag}")
    def list_items(
        request: Request,
        db: Session = Depends(get_db),
        vehicle_id: str | None = None,
        from_: date | None = Query(None, alias="from"),
        to: date | None = None,
        include_deleted: bool = False,
        limit: int = Query(500, ge=1, le=5000),
        offset: int = Query(0, ge=0),
    ):
        stmt = filtered_query(model, time_field, request, vehicle_id, from_, to, include_deleted)
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(*order_by).limit(limit).offset(offset)).all()
        items = [schema_out.model_validate(row) for row in rows]
        if decorate_items:
            decorate_items(db, request, items)
        return Page[schema_out](items=items, total=total)

    @router.get("/{item_id}", response_model=schema_out, name=f"get_{tag}")
    def get_item(item_id: str, db: Session = Depends(get_db)):
        return schema_out.model_validate(get_or_404(db, item_id))

    @router.post("", response_model=schema_out, status_code=201, name=f"create_{tag}")
    def create_item(body: schema_in, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        data = body.model_dump()
        check_vehicle(db, data)
        obj = model(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return schema_out.model_validate(obj)

    @router.patch("/{item_id}", response_model=schema_out, name=f"update_{tag}")
    def update_item(
        item_id: str,
        body: dict[str, Any] = Body(...),
        if_match: str | None = Header(None, alias="If-Match"),
        db: Session = Depends(get_db),
    ):
        obj = get_or_404(db, item_id)
        if if_match is not None and if_match.strip('"') != str(obj.version):
            raise HTTPException(409, "This record was changed in the meantime. Reload and try again.")

        current = schema_in.model_validate(obj).model_dump()
        body = dict(body)
        if prepare_patch:
            prepare_patch(obj, current, body)
        try:
            new = schema_in.model_validate({**current, **body}).model_dump()
        except ValidationError as err:
            raise RequestValidationError(err.errors()) from err
        check_vehicle(db, new)

        changed = [key for key, value in new.items() if getattr(obj, key) != value]
        if changed and getattr(obj, "source", "manual") != "manual":
            # Protect user edits of automatic records from later collector updates.
            locked = list(obj.locked_fields or [])
            auto_values = dict(obj.auto_values or {})
            for key in changed:
                if key not in locked:
                    locked.append(key)
                    old = getattr(obj, key)
                    auto_values[key] = old.isoformat() if hasattr(old, "isoformat") else old
            obj.locked_fields, obj.auto_values = locked, auto_values
        for key in changed:
            setattr(obj, key, new[key])
        obj.version += 1
        db.commit()
        db.refresh(obj)
        return schema_out.model_validate(obj)

    @router.delete("/{item_id}", status_code=204, name=f"delete_{tag}")
    def delete_item(item_id: str, db: Session = Depends(get_db)):
        obj = get_or_404(db, item_id)
        if obj.deleted_at is None:
            obj.deleted_at = utcnow()
            obj.version += 1
            db.commit()

    @router.post("/{item_id}/restore", response_model=schema_out, name=f"restore_{tag}")
    def restore_item(item_id: str, db: Session = Depends(get_db)):
        obj = get_or_404(db, item_id)
        if obj.deleted_at is not None:
            obj.deleted_at = None
            obj.version += 1
            db.commit()
            db.refresh(obj)
        return schema_out.model_validate(obj)

    return router
