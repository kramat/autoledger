"""AutoLedger Collector: turns car and charger entities into trips, charges and refuels."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .client import AutoLedgerClient, AutoLedgerError
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import SummaryCoordinator
from .runtime import Runtime

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AutoLedgerConfigEntry = ConfigEntry[Runtime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AutoLedgerConfigEntry) -> bool:
    client = AutoLedgerClient(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    runtime = Runtime(hass, entry, client)
    # Detection does not need the add-on: events wait in the outbox until it is reachable.
    await runtime.async_start()
    runtime.coordinator = SummaryCoordinator(hass, entry, client)
    await runtime.coordinator.async_refresh()
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutoLedgerConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: AutoLedgerConfigEntry) -> None:
    """Subentries added or changed: start again with the new entity mapping."""
    await hass.config_entries.async_reload(entry.entry_id)


# --- Services -------------------------------------------------------------

ATTR_VEHICLE = "vehicle"


def _runtime(hass: HomeAssistant) -> Runtime:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError("The AutoLedger Collector is not set up", translation_domain=DOMAIN,
                                 translation_key="not_loaded")


def _vehicle_id(hass: HomeAssistant, device_id: str) -> str:
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith("vehicle_"):
                return identifier.removeprefix("vehicle_")
    raise ServiceValidationError("Pick an AutoLedger vehicle", translation_domain=DOMAIN,
                                 translation_key="not_a_vehicle")


def _timestamp(call: ServiceCall) -> str:
    when = call.data.get("timestamp")
    return dt_util.as_utc(when).isoformat() if when else dt_util.utcnow().isoformat()


async def _create(hass: HomeAssistant, resource: str, body: dict) -> ServiceResponse:
    runtime = _runtime(hass)
    try:
        record = await runtime.client.create(resource, {k: v for k, v in body.items() if v is not None})
    except AutoLedgerError as err:
        raise HomeAssistantError(str(err)) from err
    await runtime.coordinator.async_request_refresh()
    return {"id": record["id"]}


def _register_services(hass: HomeAssistant) -> None:
    vehicle = {vol.Required(ATTR_VEHICLE): cv.string}
    when = {vol.Optional("timestamp"): cv.datetime}

    async def add_refuel(call: ServiceCall) -> ServiceResponse:
        data = call.data
        return await _create(hass, "refuels", {
            "vehicle_id": _vehicle_id(hass, data[ATTR_VEHICLE]),
            "ts": _timestamp(call),
            "litres": data.get("litres"),
            "total": data.get("total"),
            "price_per_l": data.get("price_per_l"),
            "odometer_km": data.get("odometer"),
            "full_tank": data.get("full_tank", True),
            "station": data.get("station"),
        })

    async def add_charge(call: ServiceCall) -> ServiceResponse:
        data = call.data
        has_total = data.get("total") is not None
        return await _create(hass, "charges", {
            "vehicle_id": _vehicle_id(hass, data[ATTR_VEHICLE]),
            "kind": "public",
            "start_ts": _timestamp(call),
            "energy_kwh": data["energy_kwh"],
            "price_mode": "total" if has_total else "per_kwh",
            "price_total": data.get("total"),
            "price_per_kwh": data.get("price_per_kwh"),
            "address": data.get("location"),
        })

    async def add_odometer(call: ServiceCall) -> ServiceResponse:
        data = call.data
        return await _create(hass, "odometer-readings", {
            "vehicle_id": _vehicle_id(hass, data[ATTR_VEHICLE]),
            "ts": _timestamp(call),
            "odometer_km": data["odometer"],
        })

    async def resync(call: ServiceCall) -> None:
        runtime = _runtime(hass)
        await runtime.outbox.flush()
        await runtime.coordinator.async_request_refresh()

    positive = vol.All(vol.Coerce(float), vol.Range(min=0))
    hass.services.async_register(DOMAIN, "add_refuel", add_refuel, schema=vol.Schema({
        **vehicle, **when,
        vol.Optional("litres"): positive, vol.Optional("total"): positive, vol.Optional("price_per_l"): positive,
        vol.Optional("odometer"): positive, vol.Optional("full_tank"): cv.boolean, vol.Optional("station"): cv.string,
    }), supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "add_charge", add_charge, schema=vol.Schema({
        **vehicle, **when,
        vol.Required("energy_kwh"): positive, vol.Optional("total"): positive,
        vol.Optional("price_per_kwh"): positive, vol.Optional("location"): cv.string,
    }), supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "add_odometer", add_odometer, schema=vol.Schema({
        **vehicle, **when, vol.Required("odometer"): positive,
    }), supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "resync", resync)
