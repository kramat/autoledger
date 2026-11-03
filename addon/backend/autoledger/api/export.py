"""CSV and XLSX export of the raw records, with the same filters as the list endpoints."""

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import today_local
from ..db import get_db
from ..xlsx import XLSX_MEDIA_TYPE, Sheet, workbook
from .crud import filtered_query

router = APIRouter(prefix="/export", tags=["export"])

# resource -> (model, input schema, output schema, time field, sort column)
RESOURCES = {
    "vehicles": (models.Vehicle, schemas.VehicleIn, schemas.VehicleOut, None, models.Vehicle.created_at),
    "refuels": (models.Refuel, schemas.RefuelIn, schemas.RefuelOut, "ts", models.Refuel.ts),
    "odometer-readings": (
        models.OdometerReading, schemas.OdometerIn, schemas.OdometerOut, "ts", models.OdometerReading.ts,
    ),
    "charges": (
        models.ChargeSession, schemas.ChargeIn, schemas.ChargeOut, "start_ts", models.ChargeSession.start_ts,
    ),
    "maintenance": (
        models.MaintenanceRecord, schemas.MaintenanceIn, schemas.MaintenanceOut, "date", models.MaintenanceRecord.date,
    ),
    "expenses": (models.Expense, schemas.ExpenseIn, schemas.ExpenseOut, "date", models.Expense.date),
    "trips": (models.Trip, schemas.TripIn, schemas.TripOut, "start_ts", models.Trip.start_ts),
    "idle-records": (models.IdleRecord, schemas.IdleIn, schemas.IdleOut, "start_ts", models.IdleRecord.start_ts),
    "maintenance-schedules": (
        models.MaintenanceSchedule, schemas.ScheduleIn, schemas.ScheduleOut, None, models.MaintenanceSchedule.created_at,
    ),
}
# Record fields after the user-facing ones, when the resource has them.
TRAILING_COLUMNS = ("cost", "auto_cost", "charger_name", "archived_at", "source", "status", "id", "created_at", "updated_at")


def table(
    db: Session, request: Request, resource: str, vehicle_id: str | None, from_: date | None, to: date | None
) -> tuple[list[str], list[list]]:
    """Columns and rows of one resource (values as Python objects)."""
    model, schema_in, schema, time_field, sort = RESOURCES[resource]
    stmt = filtered_query(model, time_field, request, vehicle_id, from_, to, include_deleted=False)
    rows = db.scalars(stmt.order_by(sort)).all()
    names = {v.id: v.name for v in db.query(models.Vehicle).all()}

    columns = list(schema_in.model_fields)
    columns += [c for c in TRAILING_COLUMNS if c in schema.model_fields]
    if "vehicle_id" in columns:
        columns.insert(columns.index("vehicle_id") + 1, "vehicle")
    result = []
    for row in rows:
        data = schema.model_validate(row).model_dump()
        data["vehicle"] = names.get(data.get("vehicle_id"), "")
        result.append([data.get(c) for c in columns])
    return columns, result


def attachment(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=content, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def csv_text(columns: list[str], rows: list[list], tz) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(v, tz) for v in row])
    return buffer.getvalue()


@router.get("/records.xlsx")
def export_all_xlsx(
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
):
    """Every record type in one workbook, one sheet each."""
    tz = request.app.state.config.tz
    sheets = [Sheet(resource, *table(db, request, resource, vehicle_id, from_, to)) for resource in RESOURCES]
    return attachment(workbook(sheets, tz), XLSX_MEDIA_TYPE, f"autoledger-records-{today_local(tz).isoformat()}.xlsx")


@router.get("/{resource}.{fmt}")
def export_resource(
    resource: str,
    fmt: str,
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
):
    if resource not in RESOURCES or fmt not in ("csv", "xlsx"):
        raise HTTPException(404, f"Unknown export {resource}.{fmt}")
    tz = request.app.state.config.tz
    columns, rows = table(db, request, resource, vehicle_id, from_, to)
    filename = f"autoledger-{resource}-{today_local(tz).isoformat()}.{fmt}"
    if fmt == "xlsx":
        return attachment(workbook([Sheet(resource, columns, rows)], tz), XLSX_MEDIA_TYPE, filename)
    return attachment(csv_text(columns, rows, tz), "text/csv; charset=utf-8", filename)


def _cell(value, tz):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(tz).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value
