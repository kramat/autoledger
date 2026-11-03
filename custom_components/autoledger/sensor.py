"""Cost and usage sensors from the add-on summary, plus live charger session values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import AutoLedgerConfigEntry
from .const import DOMAIN, SIGNAL_CHARGER_UPDATE, VERSION
from .coordinator import SummaryCoordinator, vehicle_device
from .runtime import ChargerTracker


@dataclass(frozen=True, kw_only=True)
class VehicleSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None
    monthly: bool = False  # resets at the start of each month (last_reset)
    money: bool = False


def _month(item: dict, key: str) -> Any:
    return item["period"].get(key)


def _year(item: dict, key: str) -> Any:
    return item["rolling_12m"].get(key)


def _trip_attributes(trip: dict | None) -> dict:
    trip = trip or {}
    costing = trip.get("costing") or {}
    return {
        "start_ts": trip.get("start_ts"),
        "end_ts": trip.get("end_ts"),
        "from": trip.get("start_address") or trip.get("start_zone"),
        "to": trip.get("end_address") or trip.get("end_zone"),
        "energy_kwh": costing.get("energy_kwh"),
        "fuel_l": costing.get("fuel_l"),
        "cost": costing.get("cost"),
    }


def _maintenance_attributes(item: dict) -> dict:
    """The most urgent schedule, every schedule in short, and the car's own countdown."""
    first = item.get("next_maintenance") or {}
    car = item.get("car_service") or {}
    return {
        "name": first.get("name"),
        "status": first.get("status"),
        "due_date": first.get("due_date"),
        "due_km": first.get("due_km"),
        "km_left": first.get("km_left"),
        "estimated_date": first.get("estimated_date"),
        "reason": first.get("reason"),
        "schedules": [
            {k: m.get(k) for k in ("name", "status", "estimated_date", "km_left")}
            for m in item.get("maintenance") or []
        ],
        "car_days_to_service": car.get("days_to_service"),
        "car_distance_to_service": car.get("distance_to_service"),
    }


VEHICLE_SENSORS: tuple[VehicleSensorDescription, ...] = (
    VehicleSensorDescription(
        key="cost_this_month", translation_key="cost_this_month", device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL, monthly=True, money=True, value_fn=lambda i: _month(i, "total_cost"),
    ),
    VehicleSensorDescription(
        key="energy_cost_this_month", translation_key="energy_cost_this_month",
        device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL, monthly=True, money=True,
        value_fn=lambda i: _month(i, "energy_cost"),
    ),
    VehicleSensorDescription(
        key="distance_this_month", translation_key="distance_this_month", device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS, state_class=SensorStateClass.TOTAL, monthly=True,
        suggested_display_precision=0, value_fn=lambda i: _month(i, "km"),
    ),
    VehicleSensorDescription(
        key="electricity_this_month", translation_key="electricity_this_month",
        device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL, monthly=True, suggested_display_precision=1,
        value_fn=lambda i: _month(i, "electricity_kwh"),
    ),
    VehicleSensorDescription(
        key="fuel_this_month", translation_key="fuel_this_month", device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS, state_class=SensorStateClass.TOTAL, monthly=True,
        suggested_display_precision=1, value_fn=lambda i: _month(i, "fuel_l"),
    ),
    VehicleSensorDescription(
        key="cost_per_km", translation_key="cost_per_km", suggested_display_precision=3,
        value_fn=lambda i: _year(i, "energy_cost_per_km"),
    ),
    VehicleSensorDescription(
        key="total_cost_per_km", translation_key="total_cost_per_km", suggested_display_precision=3,
        value_fn=lambda i: _year(i, "total_cost_per_km"),
    ),
    VehicleSensorDescription(
        key="fuel_consumption", translation_key="fuel_consumption", native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        value_fn=lambda i: _year(i, "fuel_l_per_100km"),
    ),
    VehicleSensorDescription(
        key="electric_consumption", translation_key="electric_consumption", native_unit_of_measurement="kWh/100 km",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        value_fn=lambda i: _year(i, "kwh_per_100km"),
        attrs_fn=lambda i: {"electric_share": _year(i, "electric_share")},
    ),
    VehicleSensorDescription(
        key="last_trip", translation_key="last_trip", device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS, suggested_display_precision=1,
        value_fn=lambda i: (i.get("last_trip") or {}).get("distance_km"),
        attrs_fn=lambda i: _trip_attributes(i.get("last_trip")),
    ),
    VehicleSensorDescription(
        key="last_charge", translation_key="last_charge", device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, suggested_display_precision=1,
        value_fn=lambda i: (i.get("last_charge") or {}).get("energy_kwh"),
        attrs_fn=lambda i: {
            k: (i.get("last_charge") or {}).get(k) for k in ("start_ts", "end_ts", "cost", "avg_price", "kind")
        },
    ),
    VehicleSensorDescription(
        key="next_maintenance", translation_key="next_maintenance", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS, suggested_display_precision=0,
        value_fn=lambda i: (i.get("next_maintenance") or {}).get("days_left"),
        attrs_fn=_maintenance_attributes,
    ),
    VehicleSensorDescription(
        key="odometer", translation_key="odometer", device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0, value_fn=lambda i: i.get("odometer_km"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AutoLedgerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    known: set[str] = set()

    @callback
    def add_vehicles() -> None:
        new = []
        for item in (coordinator.data or {}).get("vehicles", []):
            vehicle_id = item["vehicle"]["id"]
            if vehicle_id not in known:
                known.add(vehicle_id)
                new += [VehicleSensor(coordinator, entry, item["vehicle"], d) for d in VEHICLE_SENSORS]
        if new:
            async_add_entities(new)

    # The hub device carries the review counter.
    async_add_entities([ReviewItemsSensor(coordinator, entry)])
    add_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(add_vehicles))

    currency = (coordinator.data or {}).get("currency", "EUR")
    for charger in runtime.chargers.values():
        async_add_entities(
            [ChargerSessionSensor(charger, "session_energy", currency),
             ChargerSessionSensor(charger, "session_cost", currency)],
            config_subentry_id=charger.subentry_id,
        )


def hub_device(entry: AutoLedgerConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)}, name="AutoLedger", manufacturer="AutoLedger", sw_version=VERSION,
    )


class VehicleSensor(CoordinatorEntity[SummaryCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: VehicleSensorDescription

    def __init__(self, coordinator, entry, vehicle: dict, description: VehicleSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_id = vehicle["id"]
        self._attr_unique_id = f"{vehicle['id']}_{description.key}"
        self._attr_device_info = vehicle_device(vehicle)
        currency = (coordinator.data or {}).get("currency", "EUR")
        if description.money:
            self._attr_native_unit_of_measurement = currency
        elif description.key in ("cost_per_km", "total_cost_per_km"):
            self._attr_native_unit_of_measurement = f"{currency}/km"

    @property
    def _item(self) -> dict | None:
        return self.coordinator.vehicle(self._vehicle_id)

    @property
    def available(self) -> bool:
        return super().available and self._item is not None

    @property
    def native_value(self) -> Any:
        item = self._item
        return self.entity_description.value_fn(item) if item else None

    @property
    def last_reset(self) -> datetime | None:
        if not self.entity_description.monthly:
            return None
        return dt_util.start_of_local_day().replace(day=1)

    @property
    def extra_state_attributes(self) -> dict | None:
        item = self._item
        if item is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(item)


class ReviewItemsSensor(CoordinatorEntity[SummaryCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "review_items"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_review_items"
        self._attr_device_info = hub_device(entry)

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("review_count")


class ChargerSessionSensor(SensorEntity):
    """Live energy or cost of the charge session that is running now."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, charger: ChargerTracker, key: str, currency: str) -> None:
        self._charger = charger
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{charger.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"charger_{charger.subentry_id}")},
                                            name=charger.name, manufacturer="AutoLedger")
        if key == "session_energy":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_suggested_display_precision = 2
        else:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = currency
            self._attr_suggested_display_precision = 2

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CHARGER_UPDATE.format(self._charger.subentry_id), self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> float:
        machine = self._charger.machine
        return round(machine.energy_kwh if self._key == "session_energy" else machine.cost, 4)

    @property
    def extra_state_attributes(self) -> dict:
        return {"session_start": self._charger.machine.start_ts}
