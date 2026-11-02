"""Vehicle snapshots: all mapped values of a car at one moment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime

UNKNOWN_STATES = {"unknown", "unavailable", "none", ""}


def parse_float(state: str | None) -> float | None:
    if state is None or state.strip().lower() in UNKNOWN_STATES:
        return None
    try:
        return float(state)
    except ValueError:
        return None


def parse_flag(state: str | None) -> bool | None:
    """Read on/off-like states from very different integrations.

    Examples: on/off, true/false, Charging/Idle, Connected/Disconnected,
    TANK_FLAP_OPEN/TANK_FLAP_CLOSED.
    """
    if state is None:
        return None
    value = state.strip().lower()
    if value in UNKNOWN_STATES:
        return None
    if value in ("on", "true", "yes", "1", "home"):
        return True
    if value in ("off", "false", "no", "0", "not_home"):
        return False
    for negative in ("disconnect", "not_", "not ", "unplug", "closed", "idle", "stopped", "complete", "finished"):
        if negative in value:
            return False
    for positive in ("charging", "connected", "plugged", "open"):
        if positive in value:
            return True
    return None


def parse_text(state: str | None) -> str | None:
    if state is None or state.strip().lower() in UNKNOWN_STATES:
        return None
    return state


@dataclass(frozen=True)
class Snapshot:
    ts: datetime
    odometer_km: float | None = None
    trip_meter_km: float | None = None
    battery_pct: float | None = None
    fuel_l: float | None = None
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    zone: str | None = None
    charging: bool | None = None
    plugged: bool | None = None
    charger_kwh: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ts"] = self.ts.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Snapshot:
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        values["ts"] = datetime.fromisoformat(values["ts"])
        return cls(**values)

    def same_values(self, other: Snapshot) -> bool:
        """True when nothing but the timestamp differs."""
        return replace(self, ts=other.ts) == other

    @property
    def place(self) -> dict:
        return {"lat": self.lat, "lon": self.lon, "address": self.address, "zone": self.zone}


def sanitize(new: Snapshot, prev: Snapshot | None, tank_l: float | None) -> tuple[Snapshot, list[str]]:
    """Replace missing or impossible values with the previous valid value.

    Returns the cleaned snapshot and a list of reasons for the replacements.
    """
    if prev is None:
        return new, []
    notes: list[str] = []
    changes: dict = {}

    def keep(name: str, reason: str | None = None) -> None:
        changes[name] = getattr(prev, name)
        if reason:
            notes.append(reason)

    for name in ("odometer_km", "trip_meter_km", "battery_pct", "fuel_l", "lat", "lon", "address", "zone",
                 "charging", "plugged", "charger_kwh"):
        if getattr(new, name) is None:
            keep(name)

    if new.odometer_km is not None and prev.odometer_km is not None and new.odometer_km < prev.odometer_km:
        keep("odometer_km", f"odometer went down ({prev.odometer_km} → {new.odometer_km}), ignored")
    if new.battery_pct is not None and not 0 <= new.battery_pct <= 100:
        keep("battery_pct", f"battery {new.battery_pct} % is impossible, ignored")
    if new.fuel_l is not None and (new.fuel_l < 0 or (tank_l and new.fuel_l > tank_l * 1.1)):
        keep("fuel_l", f"fuel level {new.fuel_l} L is impossible, ignored")
    if new.charger_kwh is not None and prev.charger_kwh is not None and new.charger_kwh < prev.charger_kwh:
        notes.append("charger counter went down (reset), new base used")

    return replace(new, **changes), notes
