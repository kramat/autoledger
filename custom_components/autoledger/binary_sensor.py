"""Whether a home charge session is running."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutoLedgerConfigEntry
from .const import DOMAIN, SIGNAL_CHARGER_UPDATE
from .runtime import ChargerTracker


async def async_setup_entry(
    hass: HomeAssistant, entry: AutoLedgerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    for charger in entry.runtime_data.chargers.values():
        async_add_entities([SessionActiveSensor(charger)], config_subentry_id=charger.subentry_id)


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
