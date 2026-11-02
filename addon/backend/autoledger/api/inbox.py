"""Review inbox and collector ingest routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db, utcnow
from ..ingest import ingest
from ..settings_store import get_settings
from .crud import patch_object
from .resources import BY_RECORD_TYPE

router = APIRouter(tags=["review"])


def _with_record(db: Session, item: models.ReviewItem) -> schemas.ReviewItemOut:
    out = schemas.ReviewItemOut.model_validate(item, from_attributes=True)
    spec = BY_RECORD_TYPE.get(item.record_type or "")
    if spec and item.record_id:
        record = db.get(spec.model, item.record_id)
        if record is not None:
            out.record = spec.schema_out.model_validate(record).model_dump(mode="json")
    return out


@router.get("/review-items", response_model=schemas.Page[schemas.ReviewItemOut])
def list_review_items(db: Session = Depends(get_db), include_resolved: bool = False, vehicle_id: str | None = None):
    stmt = select(models.ReviewItem).where(models.ReviewItem.deleted_at.is_(None))
    if not include_resolved:
        stmt = stmt.where(models.ReviewItem.resolved_at.is_(None))
    if vehicle_id:
        stmt = stmt.where(models.ReviewItem.vehicle_id == vehicle_id)
    items = db.scalars(stmt.order_by(models.ReviewItem.created_at.desc())).all()
    return schemas.Page[schemas.ReviewItemOut](items=[_with_record(db, i) for i in items], total=len(items))


@router.post("/review-items/{item_id}/resolve", response_model=schemas.ReviewItemOut)
def resolve_review_item(item_id: str, body: schemas.ResolveIn, db: Session = Depends(get_db)):
    """Quick actions: update the record, accept it as is, delete it, or dismiss the item."""
    item = db.get(models.ReviewItem, item_id)
    if item is None:
        raise HTTPException(404, f"review item {item_id} not found")
    if item.resolved_at is not None:
        raise HTTPException(409, "This item is already resolved")

    spec = BY_RECORD_TYPE.get(item.record_type or "")
    record = db.get(spec.model, item.record_id) if spec and item.record_id else None
    if body.action in ("update", "accept", "delete") and record is None:
        raise HTTPException(400, "This item has no record to act on; dismiss it instead")

    if body.action == "update":
        patch_object(db, spec, record, body.values)
        record.status = "ok"
    elif body.action == "accept":
        record.status = "ok"
        record.version += 1
    elif body.action == "delete":
        record.deleted_at = utcnow()
        record.version += 1

    # patch_object may already have closed the item; close it (again) with this action.
    item.resolved_at = item.resolved_at or utcnow()
    item.resolution = {"action": body.action, "values": body.values}
    item.version += 1
    db.commit()
    db.refresh(item)
    return _with_record(db, item)


@router.post("/ingest", tags=["ingest"])
def ingest_events(batch: schemas.IngestBatch, db: Session = Depends(get_db)):
    """Collector events, applied idempotently by uuid."""
    return ingest(db, batch.events, get_settings(db))
