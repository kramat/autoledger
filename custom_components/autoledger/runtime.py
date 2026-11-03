"""Runtime of a config entry: vehicle and charger trackers, store and outbox."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from bisect import bisect_right
from datetime import datetime, timedelta
from functools import partial
from typing import Any
from uuid import UUID, uuid4, uuid5

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
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
    CONF_VEHICLE,
    CONF_VEHICLE_ID,
    DOMAIN,
    EVENT_CHARGE_COMPLETED,
    EVENT_MAINTENANCE_DUE,
    EVENT_REFUEL_DETECTED,
    EVENT_REVIEW_NEEDED,
    EVENT_TRIP_RECORDED,
    ROLE_ADDRESS,
    ROLE_BATTERY,
    ROLE_CAR_TIMESTAMP,
    ROLE_DISTANCE_TO_SERVICE,
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
    VEHICLE_INFO_KEYS,
    SERVICE_ROLES,
    VEHICLE_ROLES,
    VERSION,
)
from .engine.charging import ChargerParams, ChargeSessionMachine, SessionEvent
from .engine.detect import VehicleParams, detect
from .engine.maintenance import maintenance_notifications
from .engine.snapshot import Snapshot, parse_flag, parse_float, parse_text, sanitize
from .outbox import Outbox

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1
MILES = 1.609344
HISTORY = 48  # snapshots kept per vehicle for battery look-ups
# Backfilled events get uuids derived from vehicle, type and time, so a second run adds nothing.
BACKFILL_NAMESPACE = UUID("6f1c2a4e-3b7d-5e9a-8c1f-2d4b6a8e0c13")


class Runtime:
    """Everything the Collector runs for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AutoLedgerClient) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.store: Store[dict] = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {"outbox": [], "vehicles": {}, "chargers": {}, "notified": {}}
        self.decisions: deque[str] = deque(maxlen=50)
        self.fallback_price = 0.25
        self.vehicles: dict[str, VehicleTracker] = {}
        self.chargers: dict[str, ChargerTracker] = {}
        self.outbox: Outbox | None = None
        self.coordinator = None  # set by __init__
        # The add-on knows maintenance schedules and the car's service countdown (0.4.0 and later).
        self.addon_maintenance = False
        self._unsubs: list[Callable[[], None]] = []

    # --- lifecycle --------------------------------------------------------

    async def async_start(self) -> None:
        stored = await self.store.async_load()
        if stored:
            self.data.update(stored)
            self.data.setdefault("notified", {})
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
    def emit(
        self, type_: str, vehicle_id: str | None, occurred_at: str, payload: dict, uuid: str | None = None
    ) -> None:
        self.outbox.add(
            {
                "uuid": uuid or str(uuid4()),
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
            elif event["type"] == "trip.recorded":
                self.hass.bus.async_fire(
                    EVENT_TRIP_RECORDED,
                    {**base, "distance_km": payload["distance_km"], "start_ts": payload["start_ts"],
                     "end_ts": payload["end_ts"], "kind": payload["kind"]},
                )
        if self.coordinator is not None:
            self.hass.async_create_task(self.coordinator.async_request_refresh())

    @callback
    def apply_summary(self) -> None:
        """Keep detection in step with vehicle changes made in the add-on (every summary poll)."""
        summary_items = (self.coordinator.data or {}).get("vehicles", [])
        items = {item["vehicle"]["id"]: item["vehicle"] for item in summary_items}
        for tracker in self.vehicles.values():
            if (vehicle := items.get(tracker.params.vehicle_id)) is not None:
                tracker.apply_vehicle(vehicle)
        self.addon_maintenance = any("next_maintenance" in item for item in summary_items)
        if self.coordinator.last_update_success and self.addon_maintenance:
            self._announce_maintenance(summary_items)

    @callback
    def _announce_maintenance(self, summary_items: list[dict]) -> None:
        """Fire autoledger_maintenance_due once per schedule when it becomes soon, and again when overdue."""
        notified: dict = self.data["notified"]
        changed = False
        for item in summary_items:
            vehicle = item["vehicle"]
            fire, memory = maintenance_notifications(item.get("maintenance") or [], notified.get(vehicle["id"], {}))
            for due in fire:
                self.hass.bus.async_fire(EVENT_MAINTENANCE_DUE, {
                    "vehicle_id": vehicle["id"], "vehicle_name": vehicle["name"],
                    **{k: due.get(k) for k in ("schedule_id", "name", "status", "due_date", "due_km", "km_left",
                                               "estimated_date", "days_left", "reason")},
                })
                self.log(f"{vehicle['name']}: maintenance {due['name']} is {due['status']}")
            if memory != notified.get(vehicle["id"], {}):
                notified[vehicle["id"]] = memory
                changed = True
        if changed:
            self.save_soon()

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
        self.state: dict = runtime.data["vehicles"].setdefault(
            self.subentry_id, {"last": None, "history": [], "pending_soc": []}
        )
        # The add-on's latest vehicle values (stored by apply_vehicle) win over the copy
        # made when the subentry was created, so a restart without the add-on keeps them.
        vehicle = self.state.get("vehicle") or data.get(CONF_VEHICLE, {})
        thresholds = data.get(CONF_THRESHOLDS, {})
        self.params = VehicleParams(
            vehicle_id=data[CONF_VEHICLE_ID],
            type=vehicle.get("type", "ICE"),
            tank_l=vehicle.get("tank_l"),
            battery_usable_kwh=vehicle.get("battery_usable_kwh"),
            kwh_per_pct=vehicle.get("kwh_per_pct"),
            external_charge_min_pct=thresholds.get(CONF_EXTERNAL_CHARGE_MIN_PCT, 3.0),
            refuel_min_l=thresholds.get(CONF_REFUEL_MIN_L, 3.0),
            min_distance_km=thresholds.get(CONF_MIN_TRIP_KM, 0.5),
            idle_min_pct=thresholds.get(CONF_IDLE_MIN_PCT, 1.0),
            idle_min_l=thresholds.get(CONF_IDLE_MIN_L, 0.5),
        )
        self.fuel_unit = data.get(CONF_FUEL_UNIT, "L")
        self.roles: dict[str, str] = {role: data[role] for role in VEHICLE_ROLES if data.get(role)}
        self.service_roles: dict[str, str] = {role: data[role] for role in SERVICE_ROLES if data.get(role)}
        self._unsub: Callable[[], None] | None = None
        self._pending: Callable[[], None] | None = None
        self._get: Callable[[str], State | None] = self.hass.states.get  # swapped during backfill

    @property
    def last(self) -> Snapshot | None:
        return Snapshot.from_dict(self.state["last"]) if self.state.get("last") else None

    @callback
    def apply_vehicle(self, vehicle: dict) -> bool:
        """Take type, tank and battery values from the add-on's current vehicle record."""
        info = {key: vehicle.get(key) for key in VEHICLE_INFO_KEYS}
        params = replace(
            self.params,
            type=info["type"] or self.params.type,
            tank_l=info["tank_l"],
            battery_usable_kwh=info["battery_usable_kwh"],
            kwh_per_pct=info["kwh_per_pct"],
        )
        if params == self.params:
            return False
        self.params = params
        self.state["vehicle"] = info
        self.runtime.save_soon()
        self.runtime.log(
            f"{self.name}: vehicle values from the add-on: tank {params.tank_l} L, "
            f"battery {params.battery_usable_kwh} kWh, wall {params.kwh_per_pct} kWh/%"
        )
        return True

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
        state = self._get(entity_id) if entity_id else None
        return state.state if state else None

    def _number(self, role: str) -> float | None:
        return parse_float(self._state(role))

    def _distance(self, role: str) -> float | None:
        value = self._number(role)
        state = self._get(self.roles.get(role, ""))
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
            state = self._get(self.roles[ROLE_TRACKER])
            if state:
                lat, lon = state.attributes.get("latitude"), state.attributes.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        return self._number(ROLE_LATITUDE), self._number(ROLE_LONGITUDE)

    def _timestamp(self, previous: Snapshot | None, now: datetime) -> datetime:
        reported = dt_util.parse_datetime(self._state(ROLE_CAR_TIMESTAMP) or "")
        if reported is not None:
            reported = dt_util.as_utc(reported)
            if reported <= now + timedelta(minutes=5) and (previous is None or reported > previous.ts):
                return reported
        return now

    def build(self, previous: Snapshot | None = None, now: datetime | None = None) -> Snapshot:
        """Read all mapped values; ``now`` is the moment of the states (backfill), default now."""
        lat, lon = self._position()
        zone = None
        if lat is not None and lon is not None:
            active = async_active_zone(self.hass, lat, lon)
            zone = active.name if active else None
        charger_values = [parse_float(state.state) if (state := self._get(e)) else None
                          for e in self.charger_entities()]
        charger_kwh = sum(charger_values) if charger_values and None not in charger_values else None
        return Snapshot(
            ts=self._timestamp(previous, now or dt_util.utcnow()),
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
        snapshot, notes = sanitize(self.build(previous), previous, self.params.tank_l)
        for note in notes:
            self.runtime.log(f"{self.name}: {note}")
        self._send_service_status(snapshot)
        if previous is None:
            self.state["since"] = dt_util.utcnow().isoformat()
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

    def _send_service_status(self, snapshot: Snapshot) -> None:
        """Pass the car's own service countdown to the add-on when it changed."""
        if not self.service_roles or not self.runtime.addon_maintenance:
            return
        values = {}
        for role in SERVICE_ROLES:
            state = self.hass.states.get(self.service_roles.get(role, ""))
            value = parse_float(state.state if state else None)
            if value is not None and role == ROLE_DISTANCE_TO_SERVICE and state.attributes.get(
                    "unit_of_measurement") == "mi":
                value *= MILES
            values[role] = value
        if all(v is None for v in values.values()) or values == self.state.get("service"):
            return
        self.state["service"] = values
        self.runtime.emit("service.status", self.params.vehicle_id, snapshot.ts.isoformat(),
                          {**values, "odometer_km": snapshot.odometer_km})
        self.runtime.save_soon()

    # --- backfill -----------------------------------------------------------

    def tracking_since(self) -> datetime | None:
        """When live tracking began: backfill stops there, so nothing is detected twice."""
        if self.state.get("since"):
            return dt_util.parse_datetime(self.state["since"])
        history = self.state.get("history") or []
        return dt_util.parse_datetime(history[0][0]) if history else None

    async def backfill(self, start: datetime) -> dict:
        """Replay recorder history through the detectors (docs/collector.md#backfill)."""
        end = self.tracking_since() or dt_util.utcnow()
        if start >= end:
            raise ValueError(f"The start must be before {end.isoformat()}, when live tracking began")
        entity_ids = [*self.roles.values(), *self.charger_entities()]
        history: dict[str, list[State]] = await get_instance(self.hass).async_add_executor_job(
            partial(
                get_significant_states, self.hass, start, end, entity_ids,
                include_start_time_state=True, significant_changes_only=False,
            )
        )
        car = set(self.roles.values())
        changes = sorted({s.last_updated for e in car for s in history.get(e, []) if start <= s.last_updated <= end})
        # One snapshot per burst of changes, as in live mode (SNAPSHOT_DEBOUNCE quiet seconds).
        moments = [t for t, nxt in zip(changes, [*changes[1:], None])
                   if nxt is None or (nxt - t).total_seconds() > SNAPSHOT_DEBOUNCE]

        previous: Snapshot | None = None
        snapshots = events = 0
        try:
            for moment in moments:
                states = {e: _state_at(history.get(e, []), moment) for e in entity_ids}
                self._get = states.get
                snapshot, _notes = sanitize(self.build(previous, moment), previous, self.params.tank_l)
                if previous is not None and snapshot.same_values(previous):
                    continue
                snapshots += 1
                if previous is not None:
                    for found in detect(previous, snapshot, self.params):
                        key = f"{self.params.vehicle_id}|{found.type}|{found.occurred_at}"
                        self.runtime.emit(found.type, self.params.vehicle_id, found.occurred_at, found.payload,
                                          uuid=str(uuid5(BACKFILL_NAMESPACE, key)))
                        events += 1
                previous = snapshot
        finally:
            self._get = self.hass.states.get
        self.runtime.log(f"{self.name}: backfill {start.isoformat()} → {end.isoformat()}: "
                         f"{snapshots} snapshots, {events} events")
        return {"from": start.isoformat(), "until": end.isoformat(), "snapshots": snapshots, "events": events}

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


def _state_at(states: list[State], moment: datetime) -> State | None:
    """The last state at or before ``moment`` (``states`` is in time order)."""
    index = bisect_right([s.last_updated for s in states], moment)
    return states[index - 1] if index else None


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
