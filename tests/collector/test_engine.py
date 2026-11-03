"""Collector detection logic, fed with value sequences like the reference setup's."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.autoledger.engine.charging import ChargerParams, ChargeSessionMachine
from custom_components.autoledger.engine.detect import VehicleParams, detect
from custom_components.autoledger.engine.snapshot import Snapshot, parse_flag, parse_float, sanitize

LYNK = VehicleParams(vehicle_id="lynk", type="PHEV", tank_l=51, battery_usable_kwh=14.1, kwh_per_pct=0.165)


def ts(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def snap(at: str, **values) -> Snapshot:
    base = {"odometer_km": 63439, "battery_pct": 78.0, "fuel_l": 16.4, "charger_kwh": 1003.0}
    return Snapshot(ts=ts(at), **{**base, **values})


def types(found) -> list[str]:
    return [d.type for d in found]


# --- Parsing and sanitizing -----------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("Charging", True), ("Idle", False), ("Connected", True), ("Disconnected", False),
        ("TANK_FLAP_OPEN", True), ("TANK_FLAP_CLOSED", False), ("on", True), ("off", False),
        ("NOT_CHARGING", False), ("unavailable", None), ("something", None), (None, None),
    ],
)
def test_parse_flag(state, expected):
    assert parse_flag(state) is expected


def test_parse_float():
    assert parse_float("63445") == 63445
    assert parse_float("unavailable") is None
    assert parse_float("n/a") is None


def test_sanitize_keeps_last_valid_values():
    prev = snap("2026-11-02T08:27:06")
    new = Snapshot(ts=ts("2026-11-02T12:42:56"), odometer_km=63000, battery_pct=None, fuel_l=900)
    clean, notes = sanitize(new, prev, tank_l=51)
    assert clean.odometer_km == 63439  # going down is impossible
    assert clean.battery_pct == 78.0  # unavailable
    assert clean.fuel_l == 16.4  # more than the tank holds
    assert clean.charger_kwh == 1003.0
    assert len(notes) == 2


# --- Detection between snapshots ------------------------------------------


def test_lynk_round_trip_of_2_november():
    """6 km drive, battery 78 → 66.5 %, fuel 16.4 → 16.0 L: an odometer reading and a round trip."""
    prev = snap("2026-11-02T08:27:06", trip_meter_km=1375.7, zone="home", lat=52.08928, lon=4.40031)
    new = snap("2026-11-02T12:42:56", odometer_km=63445, battery_pct=66.5, fuel_l=16.0, trip_meter_km=1382.0,
               zone="home", lat=52.08929, lon=4.40030)
    found = detect(prev, new, LYNK)
    assert types(found) == ["odometer.reading", "trip.recorded"]
    assert found[0].payload["odometer_km"] == 63445
    trip = found[1].payload
    assert trip["distance_km"] == 6.3 and trip["distance_source"] == "trip_meter"
    assert trip["kind"] == "round_trip" and trip["start_ts_estimated"] is True
    assert (trip["battery_start_pct"], trip["battery_end_pct"]) == (78.0, 66.5)
    assert (trip["fuel_start_l"], trip["fuel_end_l"]) == (16.4, 16.0)
    assert trip["charged_kwh"] == 0 and trip["flags"] == []


def test_trip_meter_reset_falls_back_to_odometer():
    prev = snap("2026-11-02T08:00:00", trip_meter_km=1382.0, lat=52.0, lon=4.0)
    new = snap("2026-11-02T09:00:00", odometer_km=63459, trip_meter_km=3.1, lat=52.1, lon=4.3)
    trip = detect(prev, new, LYNK)[1].payload
    assert trip["distance_km"] == 20 and trip["distance_source"] == "odometer"
    assert trip["kind"] == "one_way"


def test_home_charge_during_a_trip_window_is_counted():
    """No report between parking and charging: the counter tells how much went in."""
    prev = snap("2026-11-02T08:00:00", battery_pct=78.0)
    new = snap("2026-11-03T06:00:00", odometer_km=63445, battery_pct=100.0, charger_kwh=1010.0)
    trip = detect(prev, new, LYNK)[1]
    assert trip.payload["charged_kwh"] == 7.0 and trip.flags == ["charge_in_window"]


def test_idle_use_while_parked():
    prev = snap("2026-11-02T18:00:00", battery_pct=66.5)
    new = snap("2026-11-03T07:30:00", battery_pct=64.0, fuel_l=16.2, zone="home")
    [idle] = detect(prev, new, LYNK)
    assert idle.type == "idle.recorded"
    assert (idle.payload["battery_start_pct"], idle.payload["battery_end_pct"]) == (66.5, 64.0)
    assert idle.payload["fuel_start_l"] is None  # 0.2 L is fuel gauge noise


def test_no_idle_while_charging_at_home():
    prev = snap("2026-11-02T18:00:00", battery_pct=66.5)
    new = snap("2026-11-03T07:30:00", battery_pct=65.0, charger_kwh=1003.5)
    assert detect(prev, new, LYNK) == []


def test_refuel_detected():
    prev = snap("2026-11-02T08:00:00")
    new = snap("2026-11-02T09:00:00", fuel_l=49.9, address="Shell Voorburg", odometer_km=63441)
    found = detect(prev, new, LYNK)
    assert types(found) == ["odometer.reading", "refuel.detected", "trip.recorded"]
    assert found[2].flags == ["refuel_in_window"]
    refuel = found[1].payload
    assert refuel["litres_estimated"] == 33.5
    assert refuel["place"]["address"] == "Shell Voorburg"


def test_public_charge_detected_when_home_charger_was_idle():
    prev = snap("2026-11-01T10:00:00", battery_pct=20.0)
    new = snap("2026-11-01T15:00:00", battery_pct=75.0, charging=True)
    [found] = detect(prev, new, LYNK)
    assert found.type == "external_charge.detected"
    assert found.payload["energy_kwh_estimated"] == pytest.approx(9.08, abs=0.01)
    assert found.payload["car_reported_charging"] is True
    assert found.flags == []


def test_home_charge_is_not_a_public_charge():
    prev = snap("2026-11-01T21:00:00", battery_pct=2.0)
    new = snap("2026-11-02T06:00:00", battery_pct=100.0, charger_kwh=1019.5)
    assert detect(prev, new, LYNK) == []


def test_battery_up_while_driving_is_flagged():
    prev = snap("2026-11-01T10:00:00", battery_pct=20.0)
    new = snap("2026-11-01T11:00:00", battery_pct=26.0, odometer_km=63480, charging=False)
    found = detect(prev, new, LYNK)
    assert types(found) == ["odometer.reading", "external_charge.detected", "trip.recorded"]
    assert found[1].flags == ["driving_in_window", "possible_engine_charge"]
    # A possible engine charge is not added to the trip: the battery rise stays a rise.
    assert found[2].payload["charged_kwh"] == 0


def test_small_changes_are_noise():
    prev = snap("2026-11-01T10:00:00")
    new = snap("2026-11-01T11:00:00", battery_pct=79.5, fuel_l=17.1)
    assert detect(prev, new, LYNK) == []


def test_vehicle_type_limits_detections():
    ice = VehicleParams(vehicle_id="up", type="ICE", tank_l=35)
    bev = VehicleParams(vehicle_id="ev", type="BEV", battery_usable_kwh=60)
    prev = snap("2026-11-01T10:00:00", battery_pct=20.0, fuel_l=5.0)
    new = snap("2026-11-01T15:00:00", battery_pct=80.0, fuel_l=30.0)
    assert types(detect(prev, new, ice)) == ["refuel.detected"]
    [charge] = detect(prev, new, bev)
    assert charge.payload["energy_kwh_estimated"] == pytest.approx(60 * 0.6 / 0.9, abs=0.01)


# --- Home charging --------------------------------------------------------

SHELLY = ChargerParams(charger_key="shelly", charger_name="Shelly EV charger")


def night_charge(machine: ChargeSessionMachine, start: datetime, restart_at: int | None = None):
    """16.5 kWh over 5.5 h in 0.25 kWh steps; price 0.19 until 02:00 then 0.15.

    The power sensor goes unavailable every few readings, like the real Shelly.
    """
    events, kwh, t = [], 1003.0, start
    for step in range(66):
        t = start + timedelta(minutes=5 * step)
        kwh = round(kwh + 0.25, 2)
        price = 0.19 if t.hour >= 22 or t.hour < 2 else 0.15
        machine.on_power(t, None if step % 4 == 0 else 3000.0)
        events += machine.on_energy(t, kwh, price, "entity")
        events += machine.tick(t)
        if restart_at == step:
            machine = ChargeSessionMachine(SHELLY, machine.to_dict())  # HA restart mid-session
    for minute in range(1, 31):  # counter stays flat after the car is full
        events += machine.tick(t + timedelta(minutes=minute))
    return machine, events


def test_night_charge_is_one_priced_session():
    machine = ChargeSessionMachine(SHELLY)
    machine.on_energy(ts("2026-11-01T22:00:00"), 1003.0, 0.19, "entity")  # baseline
    machine, events = night_charge(machine, ts("2026-11-01T22:05:00"))

    assert [e.type for e in events].count("charge.started") == 1
    assert [e.type for e in events].count("charge.completed") == 1
    assert "charge.updated" in [e.type for e in events]
    done = events[-1].payload
    assert done["energy_kwh"] == pytest.approx(16.5)
    # 22:05..01:55 = 47 steps at 0.19, 02:00..03:30 = 19 steps at 0.15
    assert done["cost"] == pytest.approx(47 * 0.25 * 0.19 + 19 * 0.25 * 0.15, abs=0.001)
    assert done["end_ts"] == "2026-11-02T03:30:00+00:00"
    assert {s["price"] for s in done["price_samples"]} == {0.19, 0.15}
    assert sum(s["kwh"] for s in done["price_samples"]) == pytest.approx(16.5)
    assert not machine.active


def test_restart_mid_session_keeps_totals():
    machine = ChargeSessionMachine(SHELLY)
    machine.on_energy(ts("2026-11-01T22:00:00"), 1003.0, 0.19, "entity")
    _, events = night_charge(machine, ts("2026-11-01T22:05:00"), restart_at=30)
    assert [e.type for e in events].count("charge.started") == 1
    assert events[-1].payload["energy_kwh"] == pytest.approx(16.5)


def test_counter_reset_and_standby_blips():
    machine = ChargeSessionMachine(SHELLY)
    t = ts("2026-11-01T12:00:00")
    machine.on_energy(t, 1003.0, 0.19, "entity")
    for minute in range(1, 4):  # 0.01 kWh blips: no session
        assert machine.on_energy(t + timedelta(minutes=minute), 1003.0 + minute * 0.01, 0.19, "entity") == []
    assert not machine.active

    machine.on_energy(t + timedelta(minutes=10), 0.0, 0.19, "entity")  # firmware reset
    events = machine.on_energy(t + timedelta(minutes=15), 2.0, 0.19, "entity")
    assert [e.type for e in events] == ["charge.started"]
    assert machine.energy_kwh == 2.0


def test_tiny_sessions_are_dropped():
    machine = ChargeSessionMachine(SHELLY)
    t = ts("2026-11-01T12:00:00")
    machine.on_energy(t, 1003.0, 0.19, "entity")
    machine.on_energy(t + timedelta(minutes=1), 1003.1, 0.19, "entity")
    assert machine.active
    assert machine.tick(t + timedelta(minutes=30)) == []
    assert not machine.active


def test_trip_meter_that_lags_behind_is_not_used():
    prev = snap("2026-11-02T08:00:00", trip_meter_km=1382.0)
    new = snap("2026-11-02T09:00:00", odometer_km=63446, trip_meter_km=1382.0)
    trip = detect(prev, new, LYNK)[1].payload
    assert trip["distance_km"] == 7 and trip["distance_source"] == "odometer"
