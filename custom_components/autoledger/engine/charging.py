"""Home charge sessions from a cumulative kWh counter.

Energy comes only from the counter, never from integrating power, so a power
sensor that drops to unavailable cannot lose energy. Every increase is priced
at the electricity price of that moment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

IDLE = "idle"
CHARGING = "charging"
FINALISING = "finalising"


@dataclass(frozen=True)
class ChargerParams:
    charger_key: str
    charger_name: str
    stop_w: float = 100.0
    min_session_kwh: float = 0.2
    start_kwh: float = 0.05
    idle_after: timedelta = timedelta(minutes=10)
    finalise_after: timedelta = timedelta(minutes=5)
    update_every: timedelta = timedelta(minutes=15)


@dataclass(frozen=True)
class SessionEvent:
    type: str  # charge.started | charge.updated | charge.completed
    occurred_at: str
    payload: dict


class ChargeSessionMachine:
    """IDLE → CHARGING → FINALISING → IDLE, see docs/collector.md#home-charge-detection."""

    def __init__(self, params: ChargerParams, state: dict[str, Any] | None = None) -> None:
        self.params = params
        state = state or {}
        self.state: str = state.get("state", IDLE)
        self.last_kwh: float | None = state.get("last_kwh")
        self.session: dict[str, Any] | None = state.get("session")
        low = state.get("power_low_since")
        self.power_low_since: datetime | None = datetime.fromisoformat(low) if low else None

    # --- persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "last_kwh": self.last_kwh,
            "session": self.session,
            "power_low_since": self.power_low_since.isoformat() if self.power_low_since else None,
        }

    # --- live values for entities -----------------------------------------

    @property
    def active(self) -> bool:
        return self.session is not None

    @property
    def energy_kwh(self) -> float:
        return self.session["energy_kwh"] if self.session else 0.0

    @property
    def cost(self) -> float:
        return self.session["cost"] if self.session else 0.0

    @property
    def session_id(self) -> str | None:
        return self.session["id"] if self.session else None

    @property
    def start_ts(self) -> str | None:
        return self.session["start_ts"] if self.session else None

    # --- inputs -----------------------------------------------------------

    def on_energy(self, ts: datetime, kwh: float, price: float, price_source: str) -> list[SessionEvent]:
        """A new valid counter value (kWh) with the electricity price at that moment."""
        if self.last_kwh is None or kwh < self.last_kwh:
            self.last_kwh = kwh  # first value, or the counter was reset
            return []
        delta = kwh - self.last_kwh
        if delta <= 0:
            return []
        if self.session is None and delta < self.params.start_kwh:
            return []  # standby blip: wait until it adds up
        self.last_kwh = kwh

        if self.session is None:
            self.session = {
                "id": f"{self.params.charger_key}-{uuid4().hex[:12]}",
                "start_ts": ts.isoformat(),
                "energy_kwh": 0.0,
                "cost": 0.0,
                "samples": [],
                "last_increase": ts.isoformat(),
                "last_update_sent": ts.isoformat(),
            }
            self.state = CHARGING
            self._add(ts, delta, price, price_source)
            return [self._event("charge.started", ts)]
        self._add(ts, delta, price, price_source)
        self.state = CHARGING
        return self._maybe_update(ts)

    def on_power(self, ts: datetime, watts: float | None) -> None:
        if watts is None or self.session is None:
            return
        if watts < self.params.stop_w:
            self.power_low_since = self.power_low_since or ts
        else:
            self.power_low_since = None

    def tick(self, ts: datetime) -> list[SessionEvent]:
        """Called every minute: handles session end and periodic progress events."""
        if self.session is None:
            return []
        last_increase = datetime.fromisoformat(self.session["last_increase"])
        quiet = ts - last_increase
        if self.state == CHARGING:
            power_low = self.power_low_since is not None and ts - self.power_low_since >= self.params.idle_after
            if power_low or quiet >= self.params.idle_after:
                self.state = FINALISING
        if self.state == FINALISING and quiet >= self.params.idle_after + self.params.finalise_after:
            return self._complete()
        return self._maybe_update(ts)

    # --- internals ----------------------------------------------------------

    def _add(self, ts: datetime, kwh: float, price: float, source: str) -> None:
        session = self.session
        session["energy_kwh"] = round(session["energy_kwh"] + kwh, 4)
        session["cost"] = round(session["cost"] + kwh * price, 5)
        session["last_increase"] = ts.isoformat()
        hour = ts.replace(minute=0, second=0, microsecond=0).isoformat()
        samples = session["samples"]
        if samples and samples[-1]["hour"] == hour and samples[-1]["price"] == price:
            samples[-1]["kwh"] = round(samples[-1]["kwh"] + kwh, 4)
        else:
            samples.append({"hour": hour, "ts": ts.isoformat(), "kwh": round(kwh, 4), "price": price,
                            "source": source})
        self.power_low_since = None

    def _maybe_update(self, ts: datetime) -> list[SessionEvent]:
        last_sent = datetime.fromisoformat(self.session["last_update_sent"])
        if ts - last_sent < self.params.update_every:
            return []
        self.session["last_update_sent"] = ts.isoformat()
        return [self._event("charge.updated", ts)]

    def _complete(self) -> list[SessionEvent]:
        session, self.session = self.session, None
        self.state = IDLE
        self.power_low_since = None
        if session["energy_kwh"] < self.params.min_session_kwh:
            return []
        end = datetime.fromisoformat(session["last_increase"])
        return [self._event("charge.completed", end, session, final=True)]

    def _event(self, type_: str, ts: datetime, session: dict | None = None, final: bool = False) -> SessionEvent:
        session = session or self.session
        payload = {
            "session_id": session["id"],
            "charger_key": self.params.charger_key,
            "charger_name": self.params.charger_name,
            "start_ts": session["start_ts"],
            "energy_kwh": session["energy_kwh"],
            "cost": round(session["cost"], 4),
        }
        if final:
            payload["end_ts"] = session["last_increase"]
            payload["price_samples"] = [
                {"ts": s["ts"], "kwh": s["kwh"], "price": s["price"], "source": s["source"]}
                for s in session["samples"]
            ]
        return SessionEvent(type_, ts.isoformat(), payload)
