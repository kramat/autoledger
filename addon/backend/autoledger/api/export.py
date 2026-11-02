"""CSV export of the raw records, with the same filters as the list endpoints."""

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import today_local
from ..db import get_db
from .crud import filtered_query

router = APIRouter(prefix="/export", tags=["export"])

# resource -> (model, input schema, output schema, time field, sort column)
RESOURCES = {
    "vehicles": (models.Vehicle, schemas.VehicleIn, schemas.VehicleOut, None, models.Vehicle.created_at),
    "refuels": (models.Refuel, schemas.RefuelIn, schemas.RefuelOut, "ts", models.Refuel.ts),
    "odometer-readings": (
        models.OdometerReading, schemas.OdometerIn, schemas.OdometerOut, "ts", models.OdometerReading.ts,
    ),
    "maintenance": (
        models.MaintenanceRecord, schemas.MaintenanceIn, schemas.MaintenanceOut, "date", models.MaintenanceRecord.date,
    ),
    "expenses": (models.Expense, schemas.ExpenseIn, schemas.ExpenseOut, "date", models.Expense.date),
}
# Record fields after the user-facing ones, when the resource has them.
TRAILING_COLUMNS = ("archived_at", "source", "status", "id", "created_at", "updated_at")


@router.get("/{resource}.csv")
def export_csv(
    resource: str,
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
):
    if resource not in RESOURCES:
        raise HTTPException(404, f"Unknown resource {resource!r}")
    model, schema_in, schema, time_field, sort = RESOURCES[resource]
    tz = request.app.state.config.tz

    stmt = filtered_query(model, time_field, request, vehicle_id, from_, to, include_deleted=False)
    rows = db.scalars(stmt.order_by(sort)).all()
    names = {v.id: v.name for v in db.query(models.Vehicle).all()}

    columns = list(schema_in.model_fields)
    columns += [c for c in TRAILING_COLUMNS if c in schema.model_fields]
    if "vehicle_id" in columns:
        columns.insert(columns.index("vehicle_id") + 1, "vehicle")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        data = schema.model_validate(row).model_dump()
        data["vehicle"] = names.get(data.get("vehicle_id"), "")
        writer.writerow([_cell(data.get(c), tz) for c in columns])

    filename = f"autoledger-{resource}-{today_local(tz).isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cell(value, tz):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(tz).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value
