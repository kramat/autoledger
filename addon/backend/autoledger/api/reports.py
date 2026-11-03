"""Reports: totals per period and group, vehicles side by side, and trends (docs/api.md#derived-data)."""

from datetime import date, timedelta
from functools import reduce
from operator import add

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book, today_local
from ..db import get_db
from ..ledger import PeriodTotals, add_months, month_start
from ..reports import GROUPS, counted_days, group_ranges, history_start, per_year, seasons
from ..settings_store import get_settings
from ..xlsx import XLSX_MEDIA_TYPE, Sheet, workbook
from .export import attachment, csv_text

router = APIRouter(prefix="/reports", tags=["reports"])

# Columns of the report export, in this order.
EXPORT_COLUMNS = (
    "km", "trip_km", "electricity_kwh", "fuel_l", "electricity_cost", "fuel_cost", "energy_cost",
    "maintenance_cost", "other_cost", "depreciation_cost", "total_cost", "energy_cost_per_km", "total_cost_per_km",
    "kwh_per_100km", "fuel_l_per_100km", "electric_share", "idle_cost", "trip_count", "charge_count",
    "refuel_count", "maintenance_count",
)


def _vehicles(db: Session, ids: list[str] | None) -> list[models.Vehicle]:
    stmt = select(models.Vehicle).where(models.Vehicle.deleted_at.is_(None))
    if ids:
        stmt = stmt.where(models.Vehicle.id.in_(ids))
    else:
        stmt = stmt.where(models.Vehicle.archived_at.is_(None))
    vehicles = db.scalars(stmt.order_by(models.Vehicle.created_at)).all()
    if ids and len(vehicles) != len(set(ids)):
        raise HTTPException(404, "Unknown vehicle")
    return list(vehicles)


def _range(request: Request, from_: date | None, to: date | None) -> tuple[date, date, date]:
    """[from, to] as local dates, by default this year up to today."""
    today = today_local(request.app.state.config.tz)
    to = to or today
    from_ = from_ or date(to.year, 1, 1)
    if from_ > to:
        raise HTTPException(400, "'from' must be on or before 'to'")
    return from_, to, today


def _ids(vehicle_id: str | None, vehicle_ids: str | None) -> list[str] | None:
    ids = [v for v in (vehicle_ids or "").split(",") if v]
    if vehicle_id:
        ids.append(vehicle_id)
    return ids or None


def period_report(
    db: Session, request: Request, ids: list[str] | None, from_: date, to: date, today: date, group: str
) -> dict:
    tz = request.app.state.config.tz
    end = to + timedelta(days=1)
    ranges = group_ranges(from_, end, group)
    days = counted_days(from_, end, today)

    vehicles, totals, grouped = [], [], []
    for vehicle in _vehicles(db, ids):
        book = load_book(db, vehicle, tz, today)
        total = book.period(from_, end)
        groups = [book.period(start, stop) for _label, start, stop in ranges]
        totals.append(total)
        grouped.append(groups)
        vehicles.append({
            "vehicle": schemas.VehicleOut.model_validate(vehicle),
            "total": total.as_dict(),
            "per_year": per_year(total, days),
            "groups": _groups(ranges, groups),
        })
    combined = reduce(add, totals, PeriodTotals())
    combined_groups = [reduce(add, column, PeriodTotals()) for column in zip(*grouped)] or [
        PeriodTotals() for _ in ranges
    ]
    return {
        "from": from_,
        "to": to,
        "group": group,
        "days": days,
        "currency": get_settings(db).currency,
        "vehicles": vehicles,
        "combined": {
            "total": combined.as_dict(),
            "per_year": per_year(combined, days),
            "groups": _groups(ranges, combined_groups),
        },
    }


def _groups(ranges, totals: list[PeriodTotals]) -> list[dict]:
    return [
        {"label": label, "from": start, "to": stop - timedelta(days=1), **total.as_dict()}
        for (label, start, stop), total in zip(ranges, totals)
    ]


@router.get("/period")
def period(
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    vehicle_ids: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    group: str = Query("month", pattern="^(" + "|".join(GROUPS) + ")$"),
):
    """Totals for [from, to] per vehicle and combined, split per month, quarter or year."""
    from_, to, today = _range(request, from_, to)
    return period_report(db, request, _ids(vehicle_id, vehicle_ids), from_, to, today, group)


@router.get("/compare")
def compare(
    request: Request,
    db: Session = Depends(get_db),
    vehicle_ids: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
):
    """Vehicles side by side for one period, with figures per year for different-length histories."""
    from_, to, today = _range(request, from_, to)
    report = period_report(db, request, _ids(None, vehicle_ids), from_, to, today, "none")
    for item in report["vehicles"]:
        del item["groups"]
    del report["combined"]["groups"]
    return report


@router.get("/trends")
def trends(
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    vehicle_ids: str | None = None,
    months: int | None = Query(None, ge=1, le=120),
):
    """Monthly series of €/km and consumption, and consumption per season.

    Without ``months`` the series starts at the vehicle's first data (at most 10 years).
    """
    tz = request.app.state.config.tz
    today = today_local(tz)
    result = []
    for vehicle in _vehicles(db, _ids(vehicle_id, vehicle_ids)):
        book = load_book(db, vehicle, tz, today)
        first = history_start(book, vehicle.start_date)
        if months is not None:
            first = add_months(today, -(months - 1))
        first = max(first, add_months(today, -119))
        monthly = []
        current = month_start(first)
        while current <= today:
            following = add_months(current, 1)
            totals = book.period(current, following)
            monthly.append({
                "month": current.strftime("%Y-%m"),
                "km": round(totals.km, 1),
                "energy_cost_per_km": _r(totals.energy_cost_per_km, 3),
                "total_cost_per_km": _r(totals.total_cost_per_km, 3),
                "kwh_per_100km": _r(totals.kwh_per_100km, 1),
                "fuel_l_per_100km": _r(totals.fuel_l_per_100km, 2),
                "electric_share": _r(totals.electric_share, 3),
                "total_cost": round(totals.total_cost, 2),
            })
            current = following
        result.append({
            "vehicle": schemas.VehicleOut.model_validate(vehicle),
            "since": month_start(first),
            "monthly": monthly,
            "seasons": seasons(book, history_start(book, vehicle.start_date)),
        })
    return {"currency": get_settings(db).currency, "vehicles": result}


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


@router.get("/period.{fmt}")
def period_export(
    fmt: str,
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    vehicle_ids: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    group: str = Query("month", pattern="^(" + "|".join(GROUPS) + ")$"),
):
    """The period report as a table: one row per vehicle and group, plus totals."""
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(404, f"Unknown format {fmt!r}")
    tz = request.app.state.config.tz
    from_, to, today = _range(request, from_, to)
    report = period_report(db, request, _ids(vehicle_id, vehicle_ids), from_, to, today, group)

    columns = ["vehicle", "period", "from", "to", *EXPORT_COLUMNS]
    entries = [(v["vehicle"].name, v) for v in report["vehicles"]]
    if len(entries) > 1:
        entries.append(("All vehicles", report["combined"]))
    detail, totals = [], []
    for name, item in entries:
        for g in item["groups"]:
            detail.append([name, g["label"], g["from"], g["to"], *(g[c] for c in EXPORT_COLUMNS)])
        totals.append([name, "total", from_, to, *(item["total"][c] for c in EXPORT_COLUMNS)])

    stem = f"autoledger-report-{from_.isoformat()}-{to.isoformat()}"
    if fmt == "csv":
        return attachment(csv_text(columns, totals + detail, tz), "text/csv; charset=utf-8", f"{stem}.csv")
    sheets = [Sheet("Totals", columns, totals)]
    if group != "none":
        sheets.append(Sheet(f"Per {group}", columns, detail))
    return attachment(workbook(sheets, tz), XLSX_MEDIA_TYPE, f"{stem}.xlsx")
