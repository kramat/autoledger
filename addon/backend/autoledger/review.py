"""Review inbox: records the system was not sure about."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .models import ReviewItem

REASONS = {
    "refuel_price": "Refuel detected: confirm the litres and price",
    "public_charge_price": "Charge away from home: enter the price",
    "possible_engine_charge": "Battery went up while driving: public charge or charged by the engine?",
    "charge_without_vehicle": "Home charge session without a vehicle",
    "rejected_event": "The collector sent data that could not be processed",
}


def add_item(
    db: Session,
    reason: str,
    *,
    vehicle_id: str | None = None,
    record_type: str | None = None,
    record_id: str | None = None,
    details: dict | None = None,
) -> ReviewItem:
    """Open a review item, unless the same record already has one for this reason."""
    if record_id is not None:
        existing = db.scalars(
            select(ReviewItem).where(
                ReviewItem.record_id == record_id,
                ReviewItem.reason == reason,
                ReviewItem.resolved_at.is_(None),
            )
        ).first()
        if existing:
            return existing
    item = ReviewItem(
        vehicle_id=vehicle_id,
        record_type=record_type,
        record_id=record_id,
        reason=reason,
        details=details or {},
    )
    db.add(item)
    return item


def resolve_for_record(db: Session, record_id: str, resolution: dict) -> int:
    """Close all open items of a record. Returns how many were closed."""
    items = db.scalars(
        select(ReviewItem).where(ReviewItem.record_id == record_id, ReviewItem.resolved_at.is_(None))
    ).all()
    for item in items:
        item.resolved_at = utcnow()
        item.resolution = resolution
        item.version += 1
    return len(items)


def open_count(db: Session) -> int:
    return len(
        db.scalars(
            select(ReviewItem.id).where(ReviewItem.resolved_at.is_(None), ReviewItem.deleted_at.is_(None))
        ).all()
    )
