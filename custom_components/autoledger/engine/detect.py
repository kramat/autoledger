"""Detect trips, idle use, refuels, public charges and odometer readings between two snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

from .snapshot import Snapshot


@dataclass(frozen=True)
class VehicleParams:
    vehicle_id: str
    type: str  # ICE | PHEV | BEV
    tank_l: float | None = None
    battery_usable_kwh: float | None = None
    kwh_per_pct: float | None = None
    external_charge_min_pct: float = 3.0
    refuel_min_l: float = 3.0
    home_kwh_tolerance: float = 0.2
    min_distance_km: float = 0.5
    idle_min_pct: float = 1.0
    idle_min_l: float = 0.5

    @property
    def has_battery(self) -> bool:
        return self.type in ("PHEV", "BEV")

    @property
    def has_tank(self) -> bool:
        return self.type in ("PHEV", "ICE")

    @property
    def wall_kwh_per_pct(self) -> float | None:
        """Wall kWh per battery %, charging losses included."""
        if self.kwh_per_pct:
            return self.kwh_per_pct
        if self.battery_usable_kwh:
            return self.battery_usable_kwh / 100 / 0.9
        return None


@dataclass(frozen=True)
class Detection:
    type: str
    occurred_at: str  # ISO timestamp
    payload: dict
    reason: str = ""
    flags: list[str] = field(default_factory=list)


def _delta(new: float | None, old: float | None) -> float | None:
    return None if new is None or old is None else new - old


def detect(prev: Snapshot, new: Snapshot, params: VehicleParams) -> list[Detection]:
    found: list[Detection] = []
    distance = _delta(new.odometer_km, prev.odometer_km) or 0.0
    driven = distance >= params.min_distance_km

    if new.odometer_km is not None and (prev.odometer_km is None or new.odometer_km != prev.odometer_km):
        found.append(
            Detection(
                "odometer.reading",
                new.ts.isoformat(),
                {"ts": new.ts.isoformat(), "odometer_km": new.odometer_km},
                f"odometer {prev.odometer_km} → {new.odometer_km} km",
            )
        )

    fuel_delta = _delta(new.fuel_l, prev.fuel_l)
    if params.has_tank and fuel_delta is not None and fuel_delta >= params.refuel_min_l:
        found.append(
            Detection(
                "refuel.detected",
                new.ts.isoformat(),
                {
                    "ts": new.ts.isoformat(),
                    "place": new.place,
                    "odometer_km": new.odometer_km,
                    "fuel_start_l": prev.fuel_l,
                    "fuel_end_l": new.fuel_l,
                    "litres_estimated": round(fuel_delta, 2),
                },
                f"fuel {prev.fuel_l} → {new.fuel_l} L",
            )
        )

    battery_delta = _delta(new.battery_pct, prev.battery_pct)
    home_kwh = _delta(new.charger_kwh, prev.charger_kwh)
    home_kwh = home_kwh if home_kwh is not None and home_kwh > 0 else 0.0
    factor = params.wall_kwh_per_pct
    external_kwh = 0.0
    if (
        params.has_battery
        and battery_delta is not None
        and battery_delta >= params.external_charge_min_pct
        and home_kwh < params.home_kwh_tolerance
        and factor
    ):
        car_charging = True if (prev.charging or new.charging) else (
            False if prev.charging is False or new.charging is False else None
        )
        flags = []
        if driven:
            flags.append("driving_in_window")
            if not car_charging:
                flags.append("possible_engine_charge")
        estimate = round(battery_delta * factor, 2)
        if "possible_engine_charge" not in flags:
            external_kwh = estimate
        found.append(
            Detection(
                "external_charge.detected",
                new.ts.isoformat(),
                {
                    "window_start": prev.ts.isoformat(),
                    "window_end": new.ts.isoformat(),
                    "place": new.place,
                    "battery_start_pct": prev.battery_pct,
                    "battery_end_pct": new.battery_pct,
                    "energy_kwh_estimated": estimate,
                    "car_reported_charging": car_charging,
                    "flags": flags,
                },
                f"battery {prev.battery_pct} → {new.battery_pct} % with {home_kwh:.2f} kWh from home",
                flags,
            )
        )

    if driven:
        found.append(_trip(prev, new, params, distance, home_kwh + external_kwh, fuel_delta))
    elif home_kwh < params.home_kwh_tolerance:
        idle = _idle(prev, new, params, battery_delta, fuel_delta)
        if idle is not None:
            found.append(idle)
    return found


ROUND_TRIP_M = 150


def _metres(a: Snapshot, b: Snapshot) -> float | None:
    if None in (a.lat, a.lon, b.lat, b.lon):
        return None
    lat1, lon1, lat2, lon2 = map(radians, (a.lat, a.lon, b.lat, b.lon))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * asin(sqrt(h))


def _trip(
    prev: Snapshot, new: Snapshot, params: VehicleParams, odometer_km: float, charged_kwh: float,
    fuel_delta: float | None,
) -> Detection:
    """One trip per segment between two car reports (docs/collector.md#snapshot-mode)."""
    # The trip meter is more precise (0.1 km) but may reset or lag behind: use it when it agrees.
    trip_km = _delta(new.trip_meter_km, prev.trip_meter_km)
    if trip_km is not None and max(odometer_km - 1, 0) <= trip_km <= odometer_km + 1:
        distance, source = trip_km, "trip_meter"
    else:
        distance, source = odometer_km, "odometer"
    metres = _metres(prev, new)
    same_zone = prev.zone is not None and prev.zone == new.zone
    kind = "round_trip" if same_zone or (metres is not None and metres <= ROUND_TRIP_M) else "one_way"
    flags = []
    if fuel_delta is not None and fuel_delta >= params.refuel_min_l:
        flags.append("refuel_in_window")
    if charged_kwh:
        flags.append("charge_in_window")
    payload = {
        "start_ts": prev.ts.isoformat(),
        "start_ts_estimated": True,
        "end_ts": new.ts.isoformat(),
        "start": prev.place,
        "end": new.place,
        "odometer_start": prev.odometer_km,
        "odometer_end": new.odometer_km,
        "distance_km": round(distance, 2),
        "distance_source": source,
        "battery_start_pct": prev.battery_pct if params.has_battery else None,
        "battery_end_pct": new.battery_pct if params.has_battery else None,
        "charged_kwh": round(charged_kwh, 3),
        "fuel_start_l": prev.fuel_l if params.has_tank else None,
        "fuel_end_l": new.fuel_l if params.has_tank else None,
        "kind": kind,
        "flags": flags,
    }
    battery = _delta(new.battery_pct, prev.battery_pct)
    reason = f"trip {distance:.1f} km ({source}), battery {battery if battery is None else round(battery, 1)} %"
    if fuel_delta is not None:
        reason += f", fuel {fuel_delta:+.1f} L"
    return Detection("trip.recorded", new.ts.isoformat(), payload, reason, flags)


def _idle(
    prev: Snapshot, new: Snapshot, params: VehicleParams, battery_delta: float | None, fuel_delta: float | None,
) -> Detection | None:
    """Energy used while parked: pre-climate, standby (docs/collector.md#idle-consumption)."""
    battery_used = params.has_battery and battery_delta is not None and -battery_delta >= params.idle_min_pct
    fuel_used = params.has_tank and fuel_delta is not None and -fuel_delta >= params.idle_min_l
    if not battery_used and not fuel_used:
        return None
    payload = {
        "start_ts": prev.ts.isoformat(),
        "end_ts": new.ts.isoformat(),
        "zone": new.zone,
        "battery_start_pct": prev.battery_pct if battery_used else None,
        "battery_end_pct": new.battery_pct if battery_used else None,
        "fuel_start_l": prev.fuel_l if fuel_used else None,
        "fuel_end_l": new.fuel_l if fuel_used else None,
    }
    return Detection("idle.recorded", new.ts.isoformat(), payload,
                     f"parked: battery {battery_delta} %, fuel {fuel_delta} L")
