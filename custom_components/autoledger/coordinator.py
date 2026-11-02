"""Polls the add-on summary for the cost sensors."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AutoLedgerAuthError, AutoLedgerClient, AutoLedgerError
from .const import DOMAIN, SUMMARY_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SummaryCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AutoLedgerClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SUMMARY_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.summary()
        except AutoLedgerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AutoLedgerError as err:
            raise UpdateFailed(str(err)) from err

    def vehicle(self, vehicle_id: str) -> dict | None:
        for item in (self.data or {}).get("vehicles", []):
            if item["vehicle"]["id"] == vehicle_id:
                return item
        return None
