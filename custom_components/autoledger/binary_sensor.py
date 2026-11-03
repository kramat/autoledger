"""Whether a home charge session is running, and whether a car needs maintenance soon."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutoLedgerConfigEntry
from .const import DOMAIN, SIGNAL_CHARGER_UPDATE
from .coordinator import SummaryCoordinator, vehicle_device
from .engine.maintenance import NOTIFY_STATUSES
from .runtime import ChargerTracker


async def async_setup_entry(
    hass: HomeAssistant, entry: AutoLedgerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    for charger in entry.runtime_data.chargers.values():
        async_add_entities([SessionActiveSensor(charger)], config_subentry_id=charger.subentry_id)

    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def add_vehicles() -> None:
        new = []
        for item in (coordinator.data or {}).get("vehicles", []):
            if "maintenance" in item and item["vehicle"]["id"] not in known:
                known.add(item["vehicle"]["id"])
                new.append(MaintenanceDueSensor(coordinator, item["vehicle"]))
        if new:
            async_add_entities(new)

    add_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(add_vehicles))


class SessionActiveSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "session_active"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, charger: ChargerTracker) -> None:
        self._charger = charger
        self._attr_unique_id = f"{charger.subentry_id}_session_active"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"charger_{charger.subentry_id}")},
                                            name=charger.name, manufacturer="AutoLedger")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CHARGER_UPDATE.format(self._charger.subentry_id), self.async_write_ha_state
            )
        )

    @property
    def is_on(self) -> bool:
        return self._charger.machine.active


class MaintenanceDueSensor(CoordinatorEntity[SummaryCoordinator], BinarySensorEntity):
    """On while a maintenance schedule of the car is due soon or overdue."""

    _attr_has_entity_name = True
    _attr_translation_key = "maintenance_due"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: SummaryCoordinator, vehicle: dict) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle["id"]
        self._attr_unique_id = f"{vehicle['id']}_maintenance_due"
        self._attr_device_info = vehicle_device(vehicle)

    @property
    def _due(self) -> list[dict] | None:
        item = self.coordinator.vehicle(self._vehicle_id)
        if item is None:
            return None
        return [m for m in item.get("maintenance") or [] if m.get("status") in NOTIFY_STATUSES]

    @property
    def available(self) -> bool:
        return super().available and self._due is not None

    @property
    def is_on(self) -> bool | None:
        due = self._due
        return None if due is None else bool(due)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "items": [
                {k: m.get(k) for k in ("name", "status", "due_date", "due_km", "km_left", "estimated_date")}
                for m in self._due or []
            ]
        }
