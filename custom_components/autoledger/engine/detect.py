"""Detect refuels, public charges and odometer readings between two snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field

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
                    "energy_kwh_estimated": round(battery_delta * factor, 2),
                    "car_reported_charging": car_charging,
                    "flags": flags,
                },
                f"battery {prev.battery_pct} → {new.battery_pct} % with {home_kwh:.2f} kWh from home",
                flags,
            )
        )
    return found
