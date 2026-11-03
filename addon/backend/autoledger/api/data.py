"""JSON backup and restore, and CSV import (docs/api.md#export-and-backup)."""

import base64
import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any, Literal

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Boolean, Date, delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import __version__, models, schemas
from ..book import today_local
from ..db import UTCDateTime, get_db, utcnow
from ..importer import FIELDS, Options, convert_row, guess_date_order, guess_decimal, guess_mapping, read_csv
from ..ledger import local_midnight
from ..migrate import alembic_config, backup_database
from .attachments import attachment_dir
from .crud import check_vehicle
from .export import attachment

router = APIRouter(tags=["data"])

BACKUP_FORMAT = "autoledger-backup"
BACKUP_FORMAT_VERSION = 1
TABLES = list(models.Base.metadata.sorted_tables)  # parents before children


def _revision(db: Session) -> str | None:
    return MigrationContext.configure(db.connection()).get_current_revision()


def _json_value(value):
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


@router.get("/backup")
def backup(request: Request, attachments: bool = False, db: Session = Depends(get_db)):
    """Every table as JSON, deleted records included. The API token is not part of it.

    With ``attachments=true`` the files of the attachments are included as base64
    under ``files``; without it only their rows are.
    """
    tz = request.app.state.config.tz
    data = {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "app_version": __version__,
        "schema_revision": _revision(db),
        "exported_at": utcnow().isoformat(),
        "tables": {
            table.name: [
                {key: _json_value(value) for key, value in row.items()}
                for row in db.execute(select(table)).mappings()
            ]
            for table in TABLES
        },
    }
    if attachments:
        folder = attachment_dir(request)
        data["files"] = {
            row.id: base64.b64encode(path.read_bytes()).decode("ascii")
            for row in db.scalars(select(models.Attachment))
            if (path := folder / row.id).is_file()
        }
    return attachment(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        "application/json",
        f"autoledger-backup-{today_local(tz).isoformat()}.json",
    )


def _known_revisions() -> list[str]:
    script = ScriptDirectory.from_config(alembic_config())
    return [rev.revision for rev in reversed(list(script.walk_revisions()))]


def _row_values(table, row: dict) -> dict:
    values = {}
    for key, value in row.items():
        column = table.columns.get(key)
        if column is None:
            raise HTTPException(422, f"Column {table.name}.{key} is unknown to this version of AutoLedger")
        if value is not None:
            if isinstance(column.type, UTCDateTime):
                value = datetime.fromisoformat(value)
            elif isinstance(column.type, Date):
                value = date.fromisoformat(value)
            elif isinstance(column.type, Boolean):
                value = bool(value)
        values[key] = value
    return values


@router.post("/restore")
def restore(
    request: Request,
    data: dict[str, Any] = Body(...),
    mode: Literal["empty", "merge"] = "empty",
    db: Session = Depends(get_db),
):
    """Load a backup.

    ``empty`` (default) only works on a database without vehicles. ``merge`` adds
    the records whose id is not there yet and leaves existing ones as they are.
    The database file is copied to /data/backups first.
    """
    if data.get("format") != BACKUP_FORMAT or not isinstance(data.get("tables"), dict):
        raise HTTPException(422, "This is not an AutoLedger backup file")
    if data.get("format_version", 0) > BACKUP_FORMAT_VERSION:
        raise HTTPException(422, "This backup was made by a newer AutoLedger. Update the add-on first.")
    revisions = _known_revisions()
    if data.get("schema_revision") not in revisions:
        raise HTTPException(422, "This backup was made by a newer AutoLedger. Update the add-on first.")
    if mode == "empty" and db.scalar(select(func.count()).select_from(models.Vehicle)):
        raise HTTPException(409, "The database already has vehicles. Restore with merge, or start from an "
                                 "empty add-on.")

    config = request.app.state.config
    stamp = utcnow().strftime("%Y%m%dT%H%M%S")
    backup_database(config.db_path, config.data_dir / "backups" / f"autoledger-before-restore-{stamp}.db")

    counts: dict[str, dict[str, int]] = {}
    for table in TABLES:
        rows = data["tables"].get(table.name) or []
        inserted = skipped = 0
        key = list(table.primary_key.columns)[0]
        if mode == "empty" and table.name == models.Setting.__tablename__:
            db.execute(delete(table))  # prices saved before the restore give way to the backup's
        existing = set(db.scalars(select(key))) if mode == "merge" else set()
        for row in rows:
            values = _row_values(table, row)
            if values.get(key.name) in existing:
                skipped += 1
                continue
            try:
                with db.begin_nested():
                    db.execute(insert(table).values(**values))
                inserted += 1
            except IntegrityError:
                if mode == "empty":
                    raise HTTPException(422, f"The backup has conflicting rows in {table.name}") from None
                skipped += 1
        counts[table.name] = {"inserted": inserted, "skipped": skipped}
    files = _restore_files(db, attachment_dir(request), data.get("files"))
    db.commit()
    return {"mode": mode, "tables": counts, "files": files}


def _restore_files(db: Session, folder, files) -> dict[str, int]:
    """Write the backup's attachment files that are not there yet and match their row."""
    written = skipped = 0
    if not isinstance(files, dict) or not files:
        return {"written": 0, "skipped": 0}
    folder.mkdir(parents=True, exist_ok=True)
    rows = {a.id: a for a in db.scalars(select(models.Attachment).where(models.Attachment.id.in_(list(files))))}
    for attachment_id, encoded in files.items():
        row, path = rows.get(attachment_id), folder / attachment_id
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            content = None
        if row is None or content is None or path.exists() or hashlib.sha256(content).hexdigest() != row.sha256:
            skipped += 1
            continue
        path.write_bytes(content)
        written += 1
    return {"written": written, "skipped": skipped}


# --- CSV import -----------------------------------------------------------

IMPORT_RESOURCES = {
    "refuels": (models.Refuel, schemas.RefuelIn),
    "maintenance": (models.MaintenanceRecord, schemas.MaintenanceIn),
    "odometer-readings": (models.OdometerReading, schemas.OdometerIn),
    "expenses": (models.Expense, schemas.ExpenseIn),
}
PREVIEW_ROWS = 50


class ImportIn(BaseModel):
    resource: Literal["refuels", "maintenance", "odometer-readings", "expenses"]
    vehicle_id: str
    content: str = Field(min_length=1, max_length=5_000_000)
    mapping: dict[str, str] | None = None  # field -> column; guessed when left out
    delimiter: str | None = Field(None, min_length=1, max_length=1)
    decimal: Literal[".", ","] | None = None
    date_order: Literal["dmy", "mdy", "ymd"] | None = None


def _is_duplicate(db: Session, resource: str, vehicle_id: str, values: dict, tz) -> bool:
    """The same record is already there, for example from an earlier import of the same file."""
    model = IMPORT_RESOURCES[resource][0]
    stmt = select(func.count()).select_from(model).where(model.vehicle_id == vehicle_id, model.deleted_at.is_(None))
    if resource in ("refuels", "odometer-readings"):
        day = values["ts"].astimezone(tz).date()
        stmt = stmt.where(model.ts >= local_midnight(day, tz), model.ts < local_midnight(day + timedelta(days=1), tz))
        if resource == "refuels":
            stmt = stmt.where(func.abs(model.litres - values["litres"]) < 0.01)
        else:
            stmt = stmt.where(func.abs(model.odometer_km - values["odometer_km"]) < 0.5)
    elif resource == "maintenance":
        stmt = stmt.where(model.date == values["date"], model.description == values["description"],
                          func.abs(model.cost - values["cost"]) < 0.005)
    else:
        stmt = stmt.where(model.date == values["date"], model.category == values["category"],
                          func.abs(model.amount - values["amount"]) < 0.005)
    return bool(db.scalar(stmt))


@router.post("/import/csv")
def import_csv(
    request: Request,
    body: ImportIn,
    commit: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Preview a CSV file (default), or import its valid rows with ``?commit=true``."""
    tz = request.app.state.config.tz
    check_vehicle(db, {"vehicle_id": body.vehicle_id})
    header, rows, delimiter = read_csv(body.content, body.delimiter)
    if not header:
        raise HTTPException(422, "The file is empty")
    mapping = body.mapping if body.mapping is not None else guess_mapping(body.resource, header)
    mapping = {field: column for field, column in mapping.items() if column in header}
    index = {column: i for i, column in enumerate(header)}

    def column_cells(field: str) -> list[str]:
        column = mapping.get(field)
        return [row[index[column]] for row in rows if column and index[column] < len(row)]

    fields = FIELDS[body.resource]
    number_cells = [c for f in fields if f.kind == "number" for c in column_cells(f.name)]
    date_cells = [c for f in fields if f.kind in ("date", "datetime") for c in column_cells(f.name)]
    options = Options(
        decimal=body.decimal or guess_decimal(number_cells),
        date_order=body.date_order or guess_date_order(date_cells),
        tz=tz,
    )

    model, schema_in = IMPORT_RESOURCES[body.resource]
    results, valid = [], []
    counts = {"ok": 0, "error": 0, "duplicate": 0}
    for line, row in enumerate(rows, start=2):
        cells = {f: row[index[c]] if index[c] < len(row) else "" for f, c in mapping.items()}
        status, error, record = "ok", None, None
        try:
            values = convert_row(body.resource, cells, options)
            record = schema_in.model_validate({**values, "vehicle_id": body.vehicle_id}).model_dump()
            if _is_duplicate(db, body.resource, body.vehicle_id, record, tz):
                status = "duplicate"
        except ValueError as err:  # includes pydantic's ValidationError
            status = "error"
            error = _message(err)
        counts[status] += 1
        if status == "ok":
            valid.append(record)
        if len(results) < PREVIEW_ROWS:
            results.append({"line": line, "status": status, "error": error,
                            "values": {k: _json_value(v) for k, v in (record or {}).items() if k != "vehicle_id"}})

    created = 0
    if commit:
        for record in valid:
            obj = model(**record)
            if hasattr(obj, "source"):
                obj.source = "import"
            db.add(obj)
            created += 1
        db.commit()

    return {
        "columns": header,
        "delimiter": delimiter,
        "decimal": options.decimal,
        "date_order": options.date_order,
        "mapping": mapping,
        "fields": [{"name": f.name, "required": f.required} for f in fields],
        "rows": results,
        "counts": counts,
        "total_rows": len(rows),
        "created": created,
    }


def _message(err: ValueError) -> str:
    if isinstance(err, ValidationError):
        parts = []
        for e in err.errors():
            loc = ".".join(str(p) for p in e.get("loc", ()))
            msg = str(e.get("msg", "invalid")).removeprefix("Value error, ")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts)
    return str(err)
