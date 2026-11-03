"""Config flow: connect to the add-on, then add vehicles and chargers as subentries."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .client import AutoLedgerAuthError, AutoLedgerClient, AutoLedgerError
from .const import (
    API_VERSION,
    CONF_ADVANCED,
    CONF_CHARGER_VEHICLE,
    CONF_ENERGY,
    CONF_EXTERNAL_CHARGE_MIN_PCT,
    CONF_IDLE_MIN_L,
    CONF_IDLE_MIN_PCT,
    CONF_MIN_TRIP_KM,
    CONF_FIXED_PRICE,
    CONF_FUEL_UNIT,
    CONF_MIN_SESSION_KWH,
    CONF_NAME,
    CONF_POWER,
    CONF_PRICE,
    CONF_REFUEL_MIN_L,
    CONF_START_W,
    CONF_STOP_W,
    CONF_SWITCH,
    CONF_THRESHOLDS,
    CONF_TOKEN,
    CONF_URL,
    CONF_VEHICLE,
    CONF_VEHICLE_ID,
    DOMAIN,
    ROLE_ADDRESS,
    ROLE_BATTERY,
    ROLE_CAR_TIMESTAMP,
    ROLE_CHARGING,
    ROLE_FUEL,
    ROLE_LATITUDE,
    ROLE_LONGITUDE,
    ROLE_ODOMETER,
    ROLE_PLUG,
    ROLE_TRACKER,
    ROLE_TRIP_METER,
    SUBENTRY_CHARGER,
    SUBENTRY_VEHICLE,
    VEHICLE_INFO_KEYS,
)

_LOGGER = logging.getLogger(__name__)
ADDON_SLUG = "autoledger"
ADDON_PORT = 8099

# Entity id endings that vehicle integrations commonly use, per role (first match wins).
SUGGESTIONS: dict[str, tuple[str, ...]] = {
    ROLE_TRIP_METER: ("_trip_meter2", "_trip_meter", "_trip_odometer"),
    ROLE_BATTERY: ("_battery_level", "_state_of_charge", "_soc", "_battery"),
    ROLE_FUEL: ("_fuel_level", "_fuel"),
    ROLE_LATITUDE: ("_latitude",),
    ROLE_LONGITUDE: ("_longitude",),
    ROLE_ADDRESS: ("_address",),
    ROLE_CHARGING: ("_charge_state", "_charging_state", "_charging_status", "_charging"),
    ROLE_PLUG: ("_charger_connection_status", "_plug_status", "_plugged_in", "_charger_connected"),
    ROLE_CAR_TIMESTAMP: ("_last_updated_by_car", "_last_update"),
}


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass


async def _validate(hass: HomeAssistant, url: str, token: str) -> dict:
    client = AutoLedgerClient(async_get_clientsession(hass), url, token)
    try:
        info = await client.info()
    except AutoLedgerAuthError as err:
        raise InvalidAuth from err
    except AutoLedgerError as err:
        raise CannotConnect from err
    if info.get("api_version") != API_VERSION:
        raise CannotConnect(f"API version {info.get('api_version')} is not supported")
    return info


def _guess_url(hass: HomeAssistant) -> str:
    """The add-on's internal hostname is its slug with dashes (e.g. 1a2b3c4d-autoledger)."""
    try:
        from homeassistant.components.hassio import get_addons_list  # noqa: PLC0415

        for addon in get_addons_list(hass):
            slug = addon.get("slug", "")
            if slug == ADDON_SLUG or slug.endswith(f"_{ADDON_SLUG}"):
                return f"http://{slug.replace('_', '-')}:{ADDON_PORT}"
    except Exception:  # noqa: BLE001 - not on a Supervisor install, or not ready yet
        pass
    return f"http://local-{ADDON_SLUG}:{ADDON_PORT}"


class AutoLedgerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_VEHICLE: VehicleSubentryFlow, SUBENTRY_CHARGER: ChargerSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._errors(user_input)
            if not errors:
                return self.async_create_entry(title="AutoLedger", data=user_input)
        defaults = user_input or {CONF_URL: _guess_url(self.hass)}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_connection_schema(), defaults),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        config = discovery_info.config
        data = {CONF_URL: f"http://{config['host']}:{config['port']}", CONF_TOKEN: config["token"]}
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=data)
        self._discovered = data
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._errors(self._discovered)
            if not errors:
                return self.async_create_entry(title="AutoLedger", data=self._discovered)
        return self.async_show_form(step_id="hassio_confirm", errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._errors(user_input)
            if not errors:
                return self.async_update_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_connection_schema(), user_input or dict(entry.data)),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The token was refused, for example after it was regenerated in the add-on."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            errors = await self._errors(data)
            if not errors:
                return self.async_update_and_abort(entry, data=data)
        schema = vol.Schema(
            {vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

    async def _errors(self, data: dict[str, Any]) -> dict[str, str]:
        try:
            await _validate(self.hass, data[CONF_URL], data[CONF_TOKEN])
        except InvalidAuth:
            return {"base": "invalid_auth"}
        except CannotConnect:
            return {"base": "cannot_connect"}
        return {}


def _connection_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }
    )


def _entity(domain: str | list[str], **kwargs: Any) -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain=domain, **kwargs))


def _number(minimum: float, maximum: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=minimum, max=maximum, step=step, unit_of_measurement=unit,
                             mode=NumberSelectorMode.BOX)
    )


class _AutoLedgerSubentryFlow(ConfigSubentryFlow):
    def _client(self) -> AutoLedgerClient | None:
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return None
        return entry.runtime_data.client


class VehicleSubentryFlow(_AutoLedgerSubentryFlow):
    """Link an add-on vehicle to its Home Assistant entities."""

    def __init__(self) -> None:
        self._vehicle: dict[str, Any] = {}
        self._odometer: str = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        client = self._client()
        if client is None:
            return self.async_abort(reason="entry_not_loaded")
        try:
            vehicles = [v for v in await client.vehicles() if not v.get("archived_at")]
        except AutoLedgerError:
            return self.async_abort(reason="cannot_connect")
        linked = {s.data.get(CONF_VEHICLE_ID) for s in self._get_entry().subentries.values()}
        available = [v for v in vehicles if v["id"] not in linked]
        if not available:
            return self.async_abort(reason="no_vehicles")

        if user_input is not None:
            self._vehicle = next(v for v in available if v["id"] == user_input[CONF_VEHICLE_ID])
            self._odometer = user_input[ROLE_ODOMETER]
            return await self.async_step_entities()

        options = [SelectOptionDict(value=v["id"], label=v["name"]) for v in available]
        schema = vol.Schema(
            {
                vol.Required(CONF_VEHICLE_ID): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(ROLE_ODOMETER): _entity("sensor"),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        vehicle_type = self._vehicle.get("type", "ICE")
        if user_input is not None:
            data = {
                CONF_VEHICLE_ID: self._vehicle["id"],
                CONF_VEHICLE: _vehicle_info(self._vehicle),
                ROLE_ODOMETER: self._odometer,
                **user_input,
            }
            return self.async_create_entry(title=self._vehicle["name"], data=data, unique_id=self._vehicle["id"])

        suggested = _suggest(self.hass, self._odometer)
        return self.async_show_form(
            step_id="entities",
            data_schema=self.add_suggested_values_to_schema(_vehicle_schema(vehicle_type), suggested),
            description_placeholders={"vehicle": self._vehicle["name"]},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        vehicle = dict(subentry.data.get(CONF_VEHICLE, {}))
        client = self._client()
        if client is not None:
            try:  # pick up changes made in the add-on (tank size, kWh per %)
                latest = {v["id"]: v for v in await client.vehicles()}.get(subentry.data[CONF_VEHICLE_ID])
                if latest:
                    vehicle = _vehicle_info(latest)
            except AutoLedgerError:
                pass
        if user_input is not None:
            data = {
                CONF_VEHICLE_ID: subentry.data[CONF_VEHICLE_ID],
                CONF_VEHICLE: vehicle,
                **user_input,
            }
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        schema = _vehicle_schema(vehicle.get("type", "ICE"), with_odometer=True)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, dict(subentry.data)),
            description_placeholders={"vehicle": subentry.title},
        )


def _vehicle_info(vehicle: dict) -> dict:
    return {key: vehicle.get(key) for key in VEHICLE_INFO_KEYS}


def _vehicle_schema(vehicle_type: str, with_odometer: bool = False) -> vol.Schema:
    fields: dict = {}
    if with_odometer:
        fields[vol.Required(ROLE_ODOMETER)] = _entity("sensor")
    fields[vol.Optional(ROLE_TRIP_METER)] = _entity("sensor")
    if vehicle_type in ("PHEV", "BEV"):
        fields[vol.Optional(ROLE_BATTERY)] = _entity("sensor")
    if vehicle_type in ("PHEV", "ICE"):
        fields[vol.Optional(ROLE_FUEL)] = _entity("sensor")
        fields[vol.Required(CONF_FUEL_UNIT, default="L")] = SelectSelector(
            SelectSelectorConfig(options=["L", "%"], translation_key="fuel_unit")
        )
    fields[vol.Optional(ROLE_TRACKER)] = _entity("device_tracker")
    fields[vol.Optional(ROLE_LATITUDE)] = _entity("sensor")
    fields[vol.Optional(ROLE_LONGITUDE)] = _entity("sensor")
    fields[vol.Optional(ROLE_ADDRESS)] = _entity("sensor")
    if vehicle_type in ("PHEV", "BEV"):
        fields[vol.Optional(ROLE_CHARGING)] = _entity(["sensor", "binary_sensor"])
        fields[vol.Optional(ROLE_PLUG)] = _entity(["sensor", "binary_sensor"])
    fields[vol.Optional(ROLE_CAR_TIMESTAMP)] = _entity("sensor")
    thresholds = {vol.Required(CONF_MIN_TRIP_KM, default=0.5): _number(0.1, 10, 0.1, "km")}
    if vehicle_type in ("PHEV", "ICE"):
        thresholds[vol.Required(CONF_REFUEL_MIN_L, default=3.0)] = _number(0.5, 50, 0.5, "L")
        thresholds[vol.Required(CONF_IDLE_MIN_L, default=0.5)] = _number(0.1, 10, 0.1, "L")
    if vehicle_type in ("PHEV", "BEV"):
        thresholds[vol.Required(CONF_EXTERNAL_CHARGE_MIN_PCT, default=3.0)] = _number(1, 50, 0.5, "%")
        thresholds[vol.Required(CONF_IDLE_MIN_PCT, default=1.0)] = _number(0.5, 20, 0.5, "%")
    fields[vol.Required(CONF_THRESHOLDS)] = section(vol.Schema(thresholds), {"collapsed": True})
    return vol.Schema(fields)


def _suggest(hass: HomeAssistant, odometer_entity: str) -> dict[str, Any]:
    """Suggest entities from the same device as the odometer, by their entity id endings."""
    registry = er.async_get(hass)
    odometer = registry.async_get(odometer_entity)
    if odometer is None or odometer.device_id is None:
        return {}
    siblings = er.async_entries_for_device(registry, odometer.device_id)
    sensors = [e.entity_id for e in siblings if e.domain in ("sensor", "binary_sensor")]
    suggested: dict[str, Any] = {}
    for role, endings in SUGGESTIONS.items():
        for ending in endings:
            match = next((e for e in sensors if e.endswith(ending) and "12v" not in e), None)
            if match:
                suggested[role] = match
                break
    tracker = next((e.entity_id for e in siblings if e.domain == "device_tracker"), None)
    if tracker:
        suggested[ROLE_TRACKER] = tracker
    fuel = hass.states.get(suggested.get(ROLE_FUEL, ""))
    if fuel is not None:
        suggested[CONF_FUEL_UNIT] = "%" if fuel.attributes.get("unit_of_measurement") == "%" else "L"
    return suggested


class ChargerSubentryFlow(_AutoLedgerSubentryFlow):
    """A home charger: its kWh counter, optional power/switch and the electricity price."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=self._schema())

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(), subentry, title=user_input[CONF_NAME], data=user_input
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(self._schema(), dict(subentry.data)),
        )

    def _schema(self) -> vol.Schema:
        vehicles = [
            SelectOptionDict(value=s.subentry_id, label=s.title)
            for s in self._get_entry().subentries.values()
            if s.subentry_type == SUBENTRY_VEHICLE
        ]
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default="Home charger"): TextSelector(),
                vol.Required(CONF_ENERGY): _entity("sensor", device_class="energy"),
                vol.Optional(CONF_CHARGER_VEHICLE): SelectSelector(
                    SelectSelectorConfig(options=vehicles, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(CONF_PRICE): _entity("sensor"),
                vol.Optional(CONF_FIXED_PRICE): _number(0, 5, 0.001, "EUR/kWh"),
                vol.Optional(CONF_POWER): _entity("sensor", device_class="power"),
                vol.Optional(CONF_SWITCH): _entity("switch"),
                vol.Required(CONF_ADVANCED): section(
                    vol.Schema(
                        {
                            vol.Required(CONF_START_W, default=500): _number(0, 22000, 50, "W"),
                            vol.Required(CONF_STOP_W, default=100): _number(0, 5000, 10, "W"),
                            vol.Required(CONF_MIN_SESSION_KWH, default=0.2): _number(0, 10, 0.1, "kWh"),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
