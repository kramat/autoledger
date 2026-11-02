"""Derived totals for the overview page and (from M2) the collector sensors."""

from datetime import date, timedelta
from functools import reduce
from operator import add

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..book import load_book, today_local
from ..db import get_db
from ..ledger import PeriodTotals, month_ranges
from ..review import open_count
from ..settings_store import get_settings

router = APIRouter(tags=["summary"])


@router.get("/summary")
def summary(
    request: Request,
    db: Session = Depends(get_db),
    vehicle_id: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    months: int = Query(12, ge=1, le=60),
):
    """Totals for [from, to] (local dates, inclusive) plus a monthly series.

    Defaults to the current month up to today.
    """
    tz = request.app.state.config.tz
    today = today_local(tz)
    to = to or today
    from_ = from_ or to.replace(day=1)
    if from_ > to:
        raise HTTPException(400, "'from' must be on or before 'to'")
    end = to + timedelta(days=1)
    ranges = month_ranges(to, months)

    stmt = select(models.Vehicle).where(models.Vehicle.deleted_at.is_(None))
    if vehicle_id:
        stmt = stmt.where(models.Vehicle.id == vehicle_id)
    else:
        stmt = stmt.where(models.Vehicle.archived_at.is_(None))
    vehicles = db.scalars(stmt.order_by(models.Vehicle.created_at)).all()
    if vehicle_id and not vehicles:
        raise HTTPException(404, f"vehicle {vehicle_id} not found")

    result_vehicles = []
    period_totals: list[PeriodTotals] = []
    monthly_totals: list[list[PeriodTotals]] = []
    for vehicle in vehicles:
        book = load_book(db, vehicle, tz, today)
        period = book.period(from_, end)
        monthly = [book.period(start, stop) for start, stop in ranges]
        period_totals.append(period)
        monthly_totals.append(monthly)

        latest = book.latest_odometer
        charges = db.scalars(
            select(models.ChargeSession)
            .where(models.ChargeSession.vehicle_id == vehicle.id, models.ChargeSession.deleted_at.is_(None))
            .order_by(models.ChargeSession.start_ts.desc())
            .limit(5)
        ).all()
        open_charge = next((c for c in charges if c.is_open), None)
        last_charge = next((c for c in charges if not c.is_open), None)
        last_refuel = db.scalars(
            select(models.Refuel)
            .where(models.Refuel.vehicle_id == vehicle.id, models.Refuel.deleted_at.is_(None))
            .order_by(models.Refuel.ts.desc())
            .limit(1)
        ).first()
        result_vehicles.append(
            {
                "vehicle": schemas.VehicleOut.model_validate(vehicle),
                "period": period.as_dict(),
                "rolling_12m": book.rolling_12_months().as_dict(),
                "odometer_km": latest.km if latest else None,
                "odometer_ts": latest.ts if latest else None,
                "odometer_points_ignored": book.dropped_points,
                "last_refuel": schemas.RefuelOut.model_validate(last_refuel) if last_refuel else None,
                "open_charge": schemas.ChargeOut.model_validate(open_charge) if open_charge else None,
                "last_charge": schemas.ChargeOut.model_validate(last_charge) if last_charge else None,
                "monthly": _monthly(ranges, monthly),
            }
        )

    combined_monthly = [reduce(add, column, PeriodTotals()) for column in zip(*monthly_totals)]
    return {
        "from": from_,
        "to": to,
        "currency": get_settings(db).currency,
        "review_count": open_count(db),
        "vehicles": result_vehicles,
        "combined": {
            "period": reduce(add, period_totals, PeriodTotals()).as_dict(),
            "monthly": _monthly(ranges, combined_monthly or [PeriodTotals() for _ in ranges]),
        },
    }


def _monthly(ranges: list[tuple[date, date]], totals: list[PeriodTotals]) -> list[dict]:
    return [
        {"month": start.strftime("%Y-%m"), **total.as_dict()}
        for (start, _stop), total in zip(ranges, totals)
    ]
