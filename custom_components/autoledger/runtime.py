"""Runtime of a config entry: vehicle and charger trackers, store and outbox."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .client import AutoLedgerClient, AutoLedgerError
from .const import (
    CONF_ADVANCED,
    CONF_CHARGER_VEHICLE,
    CONF_ENERGY,
    CONF_EXTERNAL_CHARGE_MIN_PCT,
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
    CONF_VEHICLE,
    CONF_VEHICLE_ID,
    DOMAIN,
    EVENT_CHARGE_COMPLETED,
    EVENT_REFUEL_DETECTED,
    EVENT_REVIEW_NEEDED,
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
    SIGNAL_CHARGER_UPDATE,
    SNAPSHOT_DEBOUNCE,
    SUBENTRY_CHARGER,
    SUBENTRY_VEHICLE,
    TICK_INTERVAL,
    VEHICLE_ROLES,
    VERSION,
)
from .engine.charging import ChargerParams, ChargeSessionMachine, SessionEvent
from .engine.detect import VehicleParams, detect
from .engine.snapshot import Snapshot, parse_flag, parse_float, parse_text, sanitize
from .outbox import Outbox

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1
MILES = 1.609344
HISTORY = 48  # snapshots kept per vehicle for battery look-ups


class Runtime:
    """Everything the Collector runs for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AutoLedgerClient) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.store: Store[dict] = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {"outbox": [], "vehicles": {}, "chargers": {}}
        self.decisions: deque[str] = deque(maxlen=50)
        self.fallback_price = 0.25
        self.vehicles: dict[str, VehicleTracker] = {}
        self.chargers: dict[str, ChargerTracker] = {}
        self.outbox: Outbox | None = None
        self.coordinator = None  # set by __init__
        self._unsubs: list[Callable[[], None]] = []

    # --- lifecycle --------------------------------------------------------

    async def async_start(self) -> None:
        stored = await self.store.async_load()
        if stored:
            self.data.update(stored)
        self.outbox = Outbox(self.hass, self.client, self.data["outbox"], self.save_now, self._delivered)

        try:
            self.fallback_price = (await self.client.settings())["electricity_price"]
        except AutoLedgerError as err:
            _LOGGER.info("Using the default fallback electricity price: %s", err)

        for subentry in self.entry.subentries.values():
            if subentry.subentry_type == SUBENTRY_VEHICLE:
                self.vehicles[subentry.subentry_id] = VehicleTracker(self, subentry)
        for subentry in self.entry.subentries.values():
            if subentry.subentry_type == SUBENTRY_CHARGER:
                self.chargers[subentry.subentry_id] = ChargerTracker(self, subentry)

        for tracker in (*self.vehicles.values(), *self.chargers.values()):
            tracker.start()
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, TICK_INTERVAL))
        self.outbox.schedule(5)

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        for tracker in (*self.vehicles.values(), *self.chargers.values()):
            tracker.stop()
        if self.outbox:
            self.outbox.cancel()
        await self.store.async_save(self.data)

    # --- persistence --------------------------------------------------------

    @callback
    def save_soon(self) -> None:
        self.store.async_delay_save(lambda: self.data, 5)

    @callback
    def save_now(self) -> None:
        self.store.async_delay_save(lambda: self.data, 0)

    # --- events -----------------------------------------------------------

    @callback
    def log(self, message: str) -> None:
        self.decisions.append(f"{dt_util.now().isoformat(timespec='seconds')} {message}")
        _LOGGER.debug(message)

    @callback
    def emit(self, type_: str, vehicle_id: str | None, occurred_at: str, payload: dict) -> None:
        self.outbox.add(
            {
                "uuid": str(uuid4()),
                "type": type_,
                "vehicle_id": vehicle_id,
                "source": "collector",
                "collector_version": VERSION,
                "occurred_at": occurred_at,
                "payload": payload,
            }
        )

    @callback
    def _delivered(self, batch: list[dict], result: dict) -> None:
        """Fire HA events for automations once the add-on has the record."""
        records = {a["uuid"]: a.get("record_id") for a in result.get("accepted", [])}
        for item in batch:
            event = item["event"]
            record_id = records.get(event["uuid"])
            if record_id is None:
                continue
            payload = event["payload"]
            base = {"vehicle_id": event["vehicle_id"], "record_id": record_id}
            if event["type"] == "charge.completed":
                self.hass.bus.async_fire(
                    EVENT_CHARGE_COMPLETED, {**base, "energy_kwh": payload["energy_kwh"], "cost": payload["cost"]}
                )
            elif event["type"] == "refuel.detected":
                self.hass.bus.async_fire(EVENT_REFUEL_DETECTED, {**base, "litres": payload["litres_estimated"]})
                self.hass.bus.async_fire(EVENT_REVIEW_NEEDED, {**base, "reason": "refuel_price"})
            elif event["type"] == "external_charge.detected":
                self.hass.bus.async_fire(
                    EVENT_REVIEW_NEEDED,
                    {**base, "reason": "public_charge_price", "energy_kwh": payload["energy_kwh_estimated"]},
                )
        if self.coordinator is not None:
            self.hass.async_create_task(self.coordinator.async_request_refresh())

    @callback
    def _tick(self, now: datetime) -> None:
        for charger in self.chargers.values():
            charger.tick(dt_util.utcnow())


class VehicleTracker:
    """Turns state changes of one car's entities into snapshots and detections."""

    def __init__(self, runtime: Runtime, subentry: ConfigSubentry) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.subentry_id = subentry.subentry_id
        self.name = subentry.title
        data = subentry.data
        vehicle = data.get(CONF_VEHICLE, {})
        thresholds = data.get(CONF_THRESHOLDS, {})
        self.params = VehicleParams(
            vehicle_id=data[CONF_VEHICLE_ID],
            type=vehicle.get("type", "ICE"),
            tank_l=vehicle.get("tank_l"),
            battery_usable_kwh=vehicle.get("battery_usable_kwh"),
            kwh_per_pct=vehicle.get("kwh_per_pct"),
            external_charge_min_pct=thresholds.get(CONF_EXTERNAL_CHARGE_MIN_PCT, 3.0),
            refuel_min_l=thresholds.get(CONF_REFUEL_MIN_L, 3.0),
        )
        self.fuel_unit = data.get(CONF_FUEL_UNIT, "L")
        self.roles: dict[str, str] = {role: data[role] for role in VEHICLE_ROLES if data.get(role)}
        self.state: dict = runtime.data["vehicles"].setdefault(
            self.subentry_id, {"last": None, "history": [], "pending_soc": []}
        )
        self._unsub: Callable[[], None] | None = None
        self._pending: Callable[[], None] | None = None

    @property
    def last(self) -> Snapshot | None:
        return Snapshot.from_dict(self.state["last"]) if self.state.get("last") else None

    def charger_entities(self) -> list[str]:
        return [c.energy_entity for c in self.runtime.chargers.values() if c.vehicle_subentry_id == self.subentry_id]

    @callback
    def start(self) -> None:
        # Only the car's own entities trigger a snapshot. The charger counter is read
        # at snapshot time, so its change between two car reports is the home energy.
        self._unsub = async_track_state_change_event(self.hass, list(self.roles.values()), self._changed)
        self._pending = async_call_later(self.hass, 10, self._take_snapshot)

    @callback
    def stop(self) -> None:
        if self._unsub:
            self._unsub()
        if self._pending:
            self._pending()

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"] is None:
            return
        if self._pending:
            self._pending()
        self._pending = async_call_later(self.hass, SNAPSHOT_DEBOUNCE, self._take_snapshot)

    # --- reading HA states ------------------------------------------------

    def _state(self, role: str) -> str | None:
        entity_id = self.roles.get(role)
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state else None

    def _number(self, role: str) -> float | None:
        return parse_float(self._state(role))

    def _distance(self, role: str) -> float | None:
        value = self._number(role)
        state = self.hass.states.get(self.roles.get(role, ""))
        if value is not None and state and state.attributes.get("unit_of_measurement") == "mi":
            value *= MILES
        return value

    def _fuel_litres(self) -> float | None:
        value = self._number(ROLE_FUEL)
        if value is None or self.fuel_unit != "%":
            return value
        return value * self.params.tank_l / 100 if self.params.tank_l else None

    def _position(self) -> tuple[float | None, float | None]:
        if ROLE_TRACKER in self.roles:
            state = self.hass.states.get(self.roles[ROLE_TRACKER])
            if state:
                lat, lon = state.attributes.get("latitude"), state.attributes.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        return self._number(ROLE_LATITUDE), self._number(ROLE_LONGITUDE)

    def _timestamp(self, previous: Snapshot | None) -> datetime:
        now = dt_util.utcnow()
        reported = dt_util.parse_datetime(self._state(ROLE_CAR_TIMESTAMP) or "")
        if reported is not None:
            reported = dt_util.as_utc(reported)
            if reported <= now + timedelta(minutes=5) and (previous is None or reported > previous.ts):
                return reported
        return now

    def build(self) -> Snapshot:
        previous = self.last
        lat, lon = self._position()
        zone = None
        if lat is not None and lon is not None:
            active = async_active_zone(self.hass, lat, lon)
            zone = active.name if active else None
        charger_values = [parse_float(self.hass.states.get(e).state) if self.hass.states.get(e) else None
                          for e in self.charger_entities()]
        charger_kwh = sum(charger_values) if charger_values and None not in charger_values else None
        return Snapshot(
            ts=self._timestamp(previous),
            odometer_km=self._distance(ROLE_ODOMETER),
            trip_meter_km=self._distance(ROLE_TRIP_METER),
            battery_pct=self._number(ROLE_BATTERY),
            fuel_l=self._fuel_litres(),
            lat=lat,
            lon=lon,
            address=parse_text(self._state(ROLE_ADDRESS)),
            zone=zone,
            charging=parse_flag(self._state(ROLE_CHARGING)),
            plugged=parse_flag(self._state(ROLE_PLUG)),
            charger_kwh=charger_kwh,
        )

    # --- detection --------------------------------------------------------

    @callback
    def _take_snapshot(self, _now=None) -> None:
        self._pending = None
        previous = self.last
        snapshot, notes = sanitize(self.build(), previous, self.params.tank_l)
        for note in notes:
            self.runtime.log(f"{self.name}: {note}")
        if previous is None:
            self._commit(snapshot)
            self.runtime.log(f"{self.name}: first snapshot stored as baseline")
            return
        if snapshot.same_values(previous):
            return

        for found in detect(previous, snapshot, self.params):
            self.runtime.log(f"{self.name}: {found.type} ({found.reason})")
            self.runtime.emit(found.type, self.params.vehicle_id, found.occurred_at, found.payload)
        self._commit(snapshot)
        self._send_pending_soc(snapshot)

    def _commit(self, snapshot: Snapshot) -> None:
        self.state["last"] = snapshot.to_dict()
        if snapshot.battery_pct is not None:
            history = self.state["history"]
            history.append([snapshot.ts.isoformat(), snapshot.battery_pct])
            del history[:-HISTORY]
        self.runtime.save_soon()

    def soc_at(self, when: str) -> float | None:
        """Battery % of the last snapshot at or before ``when``."""
        moment = dt_util.parse_datetime(when)
        value = None
        for ts, battery in self.state["history"]:
            if dt_util.parse_datetime(ts) <= moment:
                value = battery
        return value

    def await_soc_end(self, session_id: str, end_ts: str) -> None:
        self.state["pending_soc"].append({"session_id": session_id, "end_ts": end_ts})
        self.runtime.save_soon()

    def _send_pending_soc(self, snapshot: Snapshot) -> None:
        """Cloud cars report late: fill in the battery % after a home charge."""
        if snapshot.battery_pct is None:
            return
        remaining = []
        for pending in self.state["pending_soc"]:
            end = dt_util.parse_datetime(pending["end_ts"])
            if snapshot.ts >= end:
                if snapshot.ts - end <= timedelta(hours=12):
                    self.runtime.emit(
                        "charge.soc_update",
                        self.params.vehicle_id,
                        snapshot.ts.isoformat(),
                        {"session_id": pending["session_id"], "soc_end": snapshot.battery_pct},
                    )
            else:
                remaining.append(pending)
        self.state["pending_soc"] = remaining


class ChargerTracker:
    """Runs the charge session machine on one home charger's entities."""

    def __init__(self, runtime: Runtime, subentry: ConfigSubentry) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.subentry_id = subentry.subentry_id
        data = subentry.data
        advanced = data.get(CONF_ADVANCED, {})
        self.name = data.get(CONF_NAME) or subentry.title
        self.energy_entity: str = data[CONF_ENERGY]
        self.power_entity: str | None = data.get(CONF_POWER)
        self.switch_entity: str | None = data.get(CONF_SWITCH)
        self.price_entity: str | None = data.get(CONF_PRICE)
        self.fixed_price: float | None = data.get(CONF_FIXED_PRICE)
        self.vehicle_subentry_id: str | None = data.get(CONF_CHARGER_VEHICLE) or None
        params = ChargerParams(
            charger_key=self.subentry_id,
            charger_name=self.name,
            start_w=advanced.get(CONF_START_W, 500.0),
            stop_w=advanced.get(CONF_STOP_W, 100.0),
            min_session_kwh=advanced.get(CONF_MIN_SESSION_KWH, 0.2),
        )
        self.machine = ChargeSessionMachine(params, runtime.data["chargers"].get(self.subentry_id))
        self._unsub: Callable[[], None] | None = None

    @property
    def vehicle(self) -> VehicleTracker | None:
        return self.runtime.vehicles.get(self.vehicle_subentry_id or "")

    @callback
    def start(self) -> None:
        entities = [e for e in (self.energy_entity, self.power_entity, self.switch_entity) if e]
        self._unsub = async_track_state_change_event(self.hass, entities, self._changed)
        # Energy delivered while Home Assistant was down is in the counter.
        state = self.hass.states.get(self.energy_entity)
        if state is not None:
            self._energy(parse_float(state.state))

    @callback
    def stop(self) -> None:
        if self._unsub:
            self._unsub()

    def price(self) -> tuple[float, str]:
        if self.price_entity:
            state = self.hass.states.get(self.price_entity)
            value = parse_float(state.state) if state else None
            if value is not None:
                return value, "entity"
        if self.fixed_price is not None:
            return self.fixed_price, "fixed"
        return self.runtime.fallback_price, "fallback"

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        entity_id = event.data["entity_id"]
        if entity_id == self.energy_entity:
            self._energy(parse_float(new_state.state))
        elif entity_id == self.power_entity:
            watts = parse_float(new_state.state)
            if watts is not None and new_state.attributes.get("unit_of_measurement") == "kW":
                watts *= 1000
            self.machine.on_power(dt_util.utcnow(), watts)
        elif entity_id == self.switch_entity and parse_flag(new_state.state) is False:
            self.machine.on_power(dt_util.utcnow(), 0.0)

    def _energy(self, kwh: float | None) -> None:
        if kwh is None:
            return  # unavailable: wait for the next valid counter value
        price, source = self.price()
        self._handle(self.machine.on_energy(dt_util.utcnow(), kwh, price, source))

    @callback
    def tick(self, now: datetime) -> None:
        self._handle(self.machine.tick(now))

    def _handle(self, events: list[SessionEvent]) -> None:
        vehicle = self.vehicle
        for event in events:
            payload = dict(event.payload)
            if event.type == "charge.completed" and vehicle is not None:
                soc_start = vehicle.soc_at(payload["start_ts"])
                if soc_start is not None:
                    payload["soc_start"] = soc_start
                vehicle.await_soc_end(payload["session_id"], payload["end_ts"])
            self.runtime.log(f"{self.name}: {event.type} {payload['energy_kwh']:.2f} kWh, {payload['cost']:.2f}")
            self.runtime.emit(event.type, vehicle.params.vehicle_id if vehicle else None, event.occurred_at, payload)
        self.runtime.data["chargers"][self.subentry_id] = self.machine.to_dict()
        self.runtime.save_soon()
        async_dispatcher_send(self.hass, SIGNAL_CHARGER_UPDATE.format(self.subentry_id))
