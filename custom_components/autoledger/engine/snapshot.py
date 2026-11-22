"""Vehicle snapshots: all mapped values of a car at one moment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timedelta

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


# An odometer rise is believed when the car could have driven it since the previous snapshot.
# Reports can arrive late and out of step with their timestamps, so a rise up to
# ODOMETER_MAX_JUMP_KM is always believed; a larger one needs the time to drive it.
ODOMETER_MAX_KMH = 200.0
ODOMETER_MAX_JUMP_KM = 1500.0
# A refused odometer value that keeps coming back is the truth after all (the baseline was
# wrong, or the sensor was replaced): this many readings in a row, over at least this long.
ODOMETER_CONFIRM_READINGS = 3
ODOMETER_CONFIRM_SPAN = timedelta(minutes=30)


def _drivable(km: float, since: timedelta) -> bool:
    hours = max(since.total_seconds(), 0.0) / 3600
    return 0 <= km <= max(ODOMETER_MAX_JUMP_KM, ODOMETER_MAX_KMH * hours)


def odometer_plausible(prev: Snapshot, km: float, ts: datetime) -> bool:
    """Whether ``km`` at ``ts`` can follow the previous snapshot's odometer."""
    return prev.odometer_km is None or _drivable(km - prev.odometer_km, ts - prev.ts)


def confirm_odometer(suspects: list[list], ts: datetime, km: float) -> tuple[list[list], bool]:
    """Remember a refused odometer value; tell when the refused values have proven themselves.

    ``suspects`` is ``[[iso timestamp, km], ...]``: the refused readings so far, each one
    consistent with the one before. Returns the new list and whether to accept ``km`` as
    the new baseline. A value of 0 (what some clouds send on an error) never counts.
    """
    if km <= 0:
        return [], False
    if suspects:
        last_ts, last_km = datetime.fromisoformat(suspects[-1][0]), suspects[-1][1]
        if not _drivable(km - last_km, ts - last_ts):
            suspects = []
    suspects = [*suspects, [ts.isoformat(), km]]
    first = datetime.fromisoformat(suspects[0][0])
    return suspects, len(suspects) >= ODOMETER_CONFIRM_READINGS and ts - first >= ODOMETER_CONFIRM_SPAN


def sanitize(
    new: Snapshot, prev: Snapshot | None, tank_l: float | None, accept_odometer: bool = False
) -> tuple[Snapshot, list[str]]:
    """Replace missing or impossible values with the previous valid value.

    Returns the cleaned snapshot and a list of reasons for the replacements.
    ``accept_odometer`` takes the odometer as it is: a refused value was confirmed
    (see ``confirm_odometer``).
    """
    if prev is None:
        return new, []
    notes: list[str] = []
    changes: dict = {}

    def keep(name: str, reason: str | None = None) -> None:
        changes[name] = getattr(prev, name)
        if reason:
            notes.append(reason)

    for name in ("odometer_km", "trip_meter_km", "battery_pct", "fuel_l", "charging", "charger_kwh"):
        if getattr(new, name) is None:
            keep(name)

    # The place follows the position. A known position outside every zone has no zone: keeping the previous
    # one would put a car parked in another town at home.
    if new.lat is None or new.lon is None:
        for name in ("lat", "lon", "zone", "address"):
            keep(name)
    elif new.address is None and (new.lat, new.lon) == (prev.lat, prev.lon):
        keep("address")

    if new.odometer_km is not None and prev.odometer_km is not None and not accept_odometer:
        if new.odometer_km < prev.odometer_km:
            keep("odometer_km", f"odometer went down ({prev.odometer_km} → {new.odometer_km}), ignored")
        elif not odometer_plausible(prev, new.odometer_km, new.ts):
            keep("odometer_km", f"odometer jumped ({prev.odometer_km} → {new.odometer_km}), ignored")
    if new.battery_pct is not None and not 0 <= new.battery_pct <= 100:
        keep("battery_pct", f"battery {new.battery_pct} % is impossible, ignored")
    if new.fuel_l is not None and (new.fuel_l < 0 or (tank_l and new.fuel_l > tank_l * 1.1)):
        keep("fuel_l", f"fuel level {new.fuel_l} L is impossible, ignored")
    if new.charger_kwh is not None and prev.charger_kwh is not None and new.charger_kwh < prev.charger_kwh:
        notes.append("charger counter went down (reset), new base used")

    return replace(new, **changes), notes
