"""Detect trips, idle use, refuels, public charges and odometer readings between two snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from uuid import UUID, uuid5

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


# Public charge sessions get ids derived from vehicle and start, so live tracking and backfill agree.
PUBLIC_CHARGE_NAMESPACE = UUID("3d0f6b2c-8a41-5c7e-9b12-7e4a0c9d1f58")
# A public charge with no battery rise for this long is over, even when the car has not moved.
PUBLIC_CHARGE_QUIET = timedelta(hours=6)


def detect(prev: Snapshot, new: Snapshot, params: VehicleParams, state: dict | None = None) -> list[Detection]:
    """Everything that happened between two snapshots.

    ``state`` is the vehicle's detector memory, kept between calls: a public charge seen over
    several reports (the car's data refreshed while it charges) stays one session in it.
    """
    state = {} if state is None else state
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
    if driven or home_kwh >= params.home_kwh_tolerance or not params.has_battery:
        state.pop("public_charge", None)  # the car left, or charges at home: a public charge is over
    elif battery_delta is not None and factor:
        charge = _follow_public_charge(state, prev, new, params, factor, battery_delta)
        if charge is not None:
            found.append(charge)
    if (
        driven
        and params.has_battery
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


def _follow_public_charge(
    state: dict, prev: Snapshot, new: Snapshot, params: VehicleParams, factor: float, battery_delta: float
) -> Detection | None:
    """A battery rise while parked away from the home charger: one session per charge, however often the car reports.

    The rises of consecutive reports add up. The session is reported once its rise reaches
    ``external_charge_min_pct``, and again with every further rise under the same session id,
    so the add-on updates it instead of adding another. It ends when the battery goes down,
    the car moves or charges at home, or after PUBLIC_CHARGE_QUIET without a rise.
    """
    charge = state.get("public_charge")
    if charge is not None and (
        battery_delta < 0
        or not _same_place(charge["place"], new.place)
        or new.ts - datetime.fromisoformat(charge["end_ts"]) > PUBLIC_CHARGE_QUIET
    ):
        state.pop("public_charge")
        charge = None
    if battery_delta <= 0 or prev.battery_pct is None:
        return None
    if charge is None:
        start = prev.ts.isoformat()
        charge = {
            "session_id": f"pub-{uuid5(PUBLIC_CHARGE_NAMESPACE, f'{params.vehicle_id}|{start}')}",
            "start_ts": start,
            "start_pct": prev.battery_pct,
            "place": new.place,
            "car_charging": None,
            "sent": False,
        }
    charge["end_ts"] = new.ts.isoformat()
    charge["end_pct"] = new.battery_pct
    if prev.charging or new.charging:
        charge["car_charging"] = True
    elif charge["car_charging"] is None and (prev.charging is False or new.charging is False):
        charge["car_charging"] = False
    state["public_charge"] = charge

    rise = charge["end_pct"] - charge["start_pct"]
    if not charge["sent"] and rise < params.external_charge_min_pct:
        return None  # not enough yet: battery noise, or the start of a charge
    continued, charge["sent"] = charge["sent"], True
    return Detection(
        "external_charge.detected",
        new.ts.isoformat(),
        {
            "session_id": charge["session_id"],
            "continued": continued,
            "window_start": charge["start_ts"],
            "window_end": charge["end_ts"],
            "place": charge["place"],
            "battery_start_pct": charge["start_pct"],
            "battery_end_pct": charge["end_pct"],
            "energy_kwh_estimated": round(rise * factor, 2),
            "car_reported_charging": charge["car_charging"],
            "flags": [],
        },
        f"battery {charge['start_pct']} → {charge['end_pct']} % since {charge['start_ts']}"
        + (" (same charge)" if continued else ""),
    )


def _same_place(a: dict, b: dict) -> bool:
    """Two places are the same when they share a zone or are within ROUND_TRIP_M; unknown counts as the same."""
    if a.get("zone") is not None and a.get("zone") == b.get("zone"):
        return True
    metres = _distance(a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon"))
    return metres is None or metres <= ROUND_TRIP_M


def _metres(a: Snapshot, b: Snapshot) -> float | None:
    return _distance(a.lat, a.lon, b.lat, b.lon)


def _distance(lat_a: float | None, lon_a: float | None, lat_b: float | None, lon_b: float | None) -> float | None:
    if None in (lat_a, lon_a, lat_b, lon_b):
        return None
    lat1, lon1, lat2, lon2 = map(radians, (lat_a, lon_a, lat_b, lon_b))
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
