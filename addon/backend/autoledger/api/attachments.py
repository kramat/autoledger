"""Receipt photos and invoices of refuels, maintenance entries and expenses (docs/api.md#attachments).

Uploads are the raw file as the request body, so the add-on needs no multipart
parser and a phone photo goes straight from the file input to the server.
"""

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db, utcnow

router = APIRouter(prefix="/attachments", tags=["attachments"])

RESOURCES = {
    "refuels": models.Refuel,
    "maintenance": models.MaintenanceRecord,
    "expenses": models.Expense,
}
# Images a phone camera produces, and PDF invoices. No SVG: it can carry scripts.
MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/gif", "application/pdf",
}
MAX_SIZE = 20 * 1024 * 1024


def attachment_dir(request: Request) -> Path:
    return request.app.state.config.data_dir / "attachments"


def _get(db: Session, attachment_id: str) -> models.Attachment:
    obj = db.get(models.Attachment, attachment_id)
    if obj is None:
        raise HTTPException(404, "Attachment not found")
    return obj


def attachments_by_record(db: Session, resource: str, record_ids: list[str]) -> dict[str, list[schemas.AttachmentOut]]:
    if not record_ids:
        return {}
    rows = db.scalars(
        select(models.Attachment)
        .where(models.Attachment.resource == resource, models.Attachment.record_id.in_(record_ids),
               models.Attachment.deleted_at.is_(None))
        .order_by(models.Attachment.created_at)
    ).all()
    result: dict[str, list[schemas.AttachmentOut]] = {}
    for row in rows:
        result.setdefault(row.record_id, []).append(schemas.AttachmentOut.model_validate(row))
    return result


def decorate(resource: str):
    """``decorate_items`` hook: list responses carry each record's attachments."""

    def add(db: Session, _request: Request, items: list) -> None:
        found = attachments_by_record(db, resource, [item.id for item in items])
        for item in items:
            item.attachments = found.get(item.id, [])

    return add


@router.get("", response_model=list[schemas.AttachmentOut])
def list_attachments(resource: str, record_id: str, db: Session = Depends(get_db)):
    return attachments_by_record(db, resource, [record_id]).get(record_id, [])


@router.post("", response_model=schemas.AttachmentOut, status_code=201)
async def upload(
    request: Request,
    resource: str = Query(..., pattern="^(refuels|maintenance|expenses)$"),
    record_id: str = Query(...),
    filename: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
):
    """The file is the request body; its Content-Type says what it is."""
    mime_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if mime_type not in MIME_TYPES:
        raise HTTPException(415, "Attach a photo (JPEG, PNG, WebP, HEIC) or a PDF")
    if int(request.headers.get("content-length") or 0) > MAX_SIZE:
        raise HTTPException(413, "The file is larger than 20 MB")
    content = await request.body()
    if not content:
        raise HTTPException(422, "The file is empty")
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "The file is larger than 20 MB")
    record = db.get(RESOURCES[resource], record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(404, "Record not found")

    obj = models.Attachment(
        resource=resource, record_id=record_id, filename=Path(filename).name, mime_type=mime_type,
        size=len(content), sha256=hashlib.sha256(content).hexdigest(),
    )
    db.add(obj)
    db.flush()
    folder = attachment_dir(request)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / obj.id).write_bytes(content)
    db.commit()
    return obj


@router.get("/{attachment_id}/file")
def download(attachment_id: str, request: Request, download: bool = False, db: Session = Depends(get_db)):
    obj = _get(db, attachment_id)
    path = attachment_dir(request) / obj.id
    if not path.is_file():
        raise HTTPException(404, "The file of this attachment is missing (restored from a backup without files?)")
    return FileResponse(
        path, media_type=obj.mime_type, filename=obj.filename,
        content_disposition_type="attachment" if download else "inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"},
    )


@router.delete("/{attachment_id}", status_code=204)
def delete(attachment_id: str, db: Session = Depends(get_db)):
    """Soft delete, like records: the file stays so it can be restored."""
    obj = _get(db, attachment_id)
    if obj.deleted_at is None:
        obj.deleted_at = utcnow()
        db.commit()


@router.post("/{attachment_id}/restore", response_model=schemas.AttachmentOut)
def restore(attachment_id: str, db: Session = Depends(get_db)):
    obj = _get(db, attachment_id)
    if obj.deleted_at is not None:
        obj.deleted_at = None
        db.commit()
    return obj
