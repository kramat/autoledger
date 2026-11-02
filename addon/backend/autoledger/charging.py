"""Charge session pricing. See docs/costs.md."""

from sqlalchemy.orm import Session

from .models import ChargeSession


def session_cost(session: ChargeSession) -> float:
    fee = session.session_fee or 0.0
    if session.price_mode == "free":
        return 0.0
    if session.price_mode == "total":
        return session.price_total or 0.0
    if session.price_mode == "per_kwh":
        return session.energy_kwh * (session.price_per_kwh or 0.0) + fee
    # samples: priced by the collector per kWh increment
    return (session.auto_cost or 0.0) + fee


def update_cost(_db: Session | None, session: ChargeSession) -> None:
    session.cost = round(session_cost(session), 4)
