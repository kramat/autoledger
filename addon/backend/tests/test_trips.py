from datetime import date, datetime, timedelta

import pytest

from autoledger.ledger import ChargeData, FactorModel, RefuelData, TripData, VehicleBook

from .conftest import TZ
from .test_ingest import API, event, send


def at(day: str, hour: int = 0, minute: int = 0) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=TZ)


def trip(id_, start, end, km=10.0, b0=None, used=None, f0=None, fuel=0.0, **extra):
    return TripData(id_, start, end, km, battery_start_pct=b0, battery_used_pct=used, fuel_start_l=f0, fuel_l=fuel,
                    **extra)


def book(trips=(), charges=(), refuels=(), kwh_per_pct=0.165, **extra):
    return VehicleBook(
        tz=TZ, today=date(2026, 11, 30), start_date=date(2026, 10, 1), start_odometer_km=63000,
        trips=trips, charges=charges, refuels=refuels, kwh_per_pct=kwh_per_pct, battery_usable_kwh=14.1,
        default_kwh_price=0.19, default_l_price=2.00, **extra,
    )


# --- Cost basis -------------------------------------------------------------


def test_worked_example_2_nov():
    """docs/costs.md#worked-example-lynk--co-2-nov-2026"""
    t = trip("t", at("2026-11-02", 13), at("2026-11-02", 13, 42), km=6.3, b0=78.0, used=11.5, f0=16.4, fuel=0.4)
    cost = book([t]).trip_costs["t"]
    assert cost.energy_kwh == pytest.approx(1.8975)
    assert cost.electricity_cost == pytest.approx(0.36, abs=0.005)
    assert cost.fuel_cost == pytest.approx(0.80)
    assert round(cost.cost, 2) == 1.16
    assert round(cost.cost / 6.3, 2) == 0.18


def test_public_charge_blends_into_the_battery_price():
    t1 = trip("t1", at("2026-11-02", 8), at("2026-11-02", 9), b0=50.0, used=10.0)
    t2 = trip("t2", at("2026-11-03", 8), at("2026-11-03", 9), used=20.0)
    fast = ChargeData(at("2026-11-02", 12), 10.0, 5.90, "c", at("2026-11-02", 13), "public")
    costs = book([t1, t2], charges=[fast]).trip_costs
    # 40 % × 0.165 = 6.6 kWh left at 0.19, plus 10 kWh at 0.59
    expected_price = (6.6 * 0.19 + 5.90) / 16.6
    assert costs["t2"].kwh_price == pytest.approx(expected_price)
    assert costs["t2"].electricity_cost == pytest.approx(3.3 * expected_price)


def test_engine_charged_battery_is_free_and_fills_the_pool():
    t1 = trip("t1", at("2026-11-02", 8), at("2026-11-02", 9), b0=0.0, used=-10.0, f0=30.0, fuel=3.0)
    t2 = trip("t2", at("2026-11-02", 10), at("2026-11-02", 11), used=10.0)
    costs = book([t1, t2]).trip_costs
    assert costs["t1"].electricity_cost == 0
    assert "battery charged by the engine" in costs["t1"].notes
    assert costs["t2"].electricity_cost == 0  # what the engine put in costs nothing extra
    assert costs["t1"].fuel_cost == pytest.approx(6.0)


def test_home_charge_in_the_same_window_counts_as_used():
    t = trip("t", at("2026-11-02", 8), at("2026-11-02", 23), b0=78.0, used=-22.0, charged_kwh=7.0)
    cost = book([t]).trip_costs["t"]
    assert cost.energy_kwh == pytest.approx(7.0 - 22 * 0.165)


def test_empty_pool_is_priced_at_default_and_flagged():
    t = trip("t", at("2026-11-02", 8), at("2026-11-02", 9), b0=10.0, used=30.0)
    cost = book([t]).trip_costs["t"]
    assert cost.electricity_cost == pytest.approx(30 * 0.165 * 0.19)
    assert any("ran empty" in note for note in cost.notes)


def test_fuel_reconciliation_spreads_by_distance():
    a = RefuelData("a", at("2026-11-01", 12), 30.0, 60.0, True, 63005)
    b = RefuelData("b", at("2026-11-05", 12), 3.0, 6.0, True, 63045)
    first = trip("first", at("2026-11-01", 8), at("2026-11-01", 9), km=5, f0=10.0, fuel=0.0)
    t1 = trip("t1", at("2026-11-02", 8), at("2026-11-02", 9), km=10, fuel=0.2)
    t2 = trip("t2", at("2026-11-03", 8), at("2026-11-03", 9), km=30, fuel=1.0)
    costs = book([first, t1, t2], refuels=[a, b], kwh_per_pct=None).trip_costs
    assert costs["t1"].fuel_l == pytest.approx(0.65)
    assert costs["t2"].fuel_l == pytest.approx(2.35)
    assert costs["t1"].fuel_reconciled and not costs["first"].fuel_reconciled


def test_no_reconciliation_when_drives_are_missing():
    """Trips cover 40 of 400 km between the full tanks: their fuel stays provisional."""
    a = RefuelData("a", at("2026-11-01", 12), 30.0, 60.0, True, 63005)
    b = RefuelData("b", at("2026-11-05", 12), 25.0, 50.0, True, 63405)
    t1 = trip("t1", at("2026-11-02", 8), at("2026-11-02", 9), km=10, f0=10.0, fuel=0.2)
    t2 = trip("t2", at("2026-11-03", 8), at("2026-11-03", 9), km=30, fuel=1.0)
    costs = book([t1, t2], refuels=[a, b], kwh_per_pct=None).trip_costs
    assert costs["t2"].fuel_l == 1.0 and not costs["t2"].fuel_reconciled


# --- kWh per percent ----------------------------------------------------------


def home(id_, day, kwh, soc0, soc1):
    return ChargeData(at(day, 22), kwh, kwh * 0.19, id_, at(day, 23) + timedelta(hours=4), "home", soc0, soc1)


def test_factor_is_learned_from_home_sessions():
    sessions = [
        home("a", "2026-11-01", 16.0, 0, 100),  # 0.160
        home("b", "2026-11-02", 8.4, 50, 100),  # 0.168
        home("c", "2026-11-03", 5.0, 70, 100),  # 0.1667
        home("d", "2026-11-04", 2.0, 90, 100),  # too small to learn from
    ]
    model = FactorModel(None, 14.1, sessions)
    assert model.at(at("2026-11-02")).mode == "default"
    assert model.at(at("2026-11-02")).value == pytest.approx(14.1 / 100 / 0.9, abs=1e-4)
    learned = model.at()
    assert learned.mode == "learned" and learned.value == pytest.approx(0.1667, abs=1e-4)
    assert learned.sessions == ("a", "b", "c")
    assert FactorModel(0.17, 14.1, sessions).at().mode == "manual"


def test_implausible_sessions_are_not_learned_from():
    sessions = [home(i, f"2026-11-0{n}", 16.0, 66.5, 100) for n, i in enumerate("abc", 1)]  # 0.48 kWh/%
    assert FactorModel(None, 14.1, sessions).at().mode == "default"


# --- Period totals ------------------------------------------------------------


def test_purchases_count_until_the_first_trip_then_use_counts():
    before = RefuelData("r1", at("2026-10-10", 12), 40.0, 80.0, True)
    after = RefuelData("r2", at("2026-11-10", 12), 20.0, 40.0, False)
    charge = ChargeData(at("2026-11-05", 22), 10.0, 1.90, "c", at("2026-11-06", 2), "home")
    trips = [
        trip("t1", at("2026-11-02", 8), at("2026-11-02", 9), km=20, b0=80.0, used=20.0, f0=16.0, fuel=0.0),
        trip("t2", at("2026-11-12", 8), at("2026-11-12", 9), km=50, used=10.0, fuel=2.5),
        TripData("idle", at("2026-11-13", 6), at("2026-11-13", 8), battery_used_pct=2.0, idle=True),
    ]
    b = book(trips, charges=[charge], refuels=[before, after])
    october = b.period(date(2026, 10, 1), date(2026, 11, 1))
    assert october.fuel_cost == 80.0 and october.trip_count == 0
    november = b.period(date(2026, 11, 1), date(2026, 12, 1))
    assert november.refuel_count == 1 and november.charge_count == 1
    assert november.trip_count == 2 and november.trip_km == 70
    assert november.electric_km == 20  # t2 used 0.05 L/km: not electric
    assert november.idle_kwh == pytest.approx(0.33)
    assert november.trip_based
    assert november.energy_cost_per_km == pytest.approx(november.trip_cost / 70)
    assert november.energy_cost == pytest.approx(november.trip_cost + november.idle_cost)
    assert november.kwh_per_100km == pytest.approx(30 * 0.165 / 70 * 100)


# --- API ------------------------------------------------------------------------


@pytest.fixture
def lynk(client):
    client.put(f"{API}/settings", json={"electricity_price": 0.19})
    response = client.post(
        f"{API}/vehicles",
        json={"name": "Lynk & Co 01", "type": "PHEV", "fuel_type": "petrol", "tank_l": 42, "battery_usable_kwh": 14.1,
              "kwh_per_pct": 0.165, "start_odometer_km": 63000, "start_date": "2026-10-01"},
    )
    return response.json()


def trip_payload(**overrides):
    payload = {
        "start_ts": "2026-11-02T12:20:00Z", "end_ts": "2026-11-02T12:42:56Z",
        "start": {"address": "Duinmeierij 118", "zone": "home"}, "end": {"address": "Duinmeierij 118", "zone": "home"},
        "odometer_start": 63439, "odometer_end": 63445, "distance_km": 6.3, "distance_source": "trip_meter",
        "battery_start_pct": 78.0, "battery_end_pct": 66.5, "fuel_start_l": 16.4, "fuel_end_l": 16.0,
        "kind": "round_trip",
    }
    return {**payload, **overrides}


def trips(client):
    return client.get(f"{API}/trips").json()["items"]


def test_trip_ingest_and_costing(client, lynk):
    send(client, event("trip.recorded", trip_payload(), lynk["id"]))
    [item] = trips(client)
    assert item["battery_used_pct"] == 11.5 and item["fuel_l"] == 0.4
    assert item["costing"]["cost"] == 1.16
    assert item["costing"]["factor_mode"] == "manual"
    summary = client.get(f"{API}/summary", params={"from": "2026-11-01", "to": "2026-11-30"}).json()
    vehicle = summary["vehicles"][0]
    assert vehicle["last_trip"]["costing"]["cost"] == 1.16
    assert vehicle["period"]["trip_km"] == 6.3
    assert vehicle["efficiency"]["mode"] == "manual"


def test_fuel_rise_counts_as_no_use(client, lynk):
    send(client, event("trip.recorded", trip_payload(fuel_end_l=16.6), lynk["id"]))
    assert trips(client)[0]["fuel_l"] == 0


def test_edit_energy_locks_it(client, lynk):
    send(client, event("trip.recorded", trip_payload(), lynk["id"]))
    trip_id = trips(client)[0]["id"]
    response = client.patch(f"{API}/trips/{trip_id}", json={"energy_kwh": 2.5})
    assert response.status_code == 200, response.text
    assert "energy_kwh" in response.json()["locked_fields"]
    item = trips(client)[0]
    assert item["costing"]["energy_kwh"] == 2.5 and "energy set by hand" in item["costing"]["notes"]


def test_split_and_merge(client, lynk):
    send(client, event("trip.recorded", trip_payload(), lynk["id"]))
    original = trips(client)[0]
    response = client.post(f"{API}/trips/{original['id']}/split",
                           json={"at_km": 2.1, "at_ts": "2026-11-02T12:30:00Z", "address": "Albert Heijn"})
    assert response.status_code == 200, response.text
    a, b = response.json()
    assert a["distance_km"] == 2.1 and b["distance_km"] == 4.2
    assert a["end_address"] == b["start_address"] == "Albert Heijn"
    assert a["costing"]["cost"] + b["costing"]["cost"] == pytest.approx(1.16, abs=0.011)
    assert {t["id"] for t in trips(client)} == {a["id"], b["id"]}

    bad = client.post(f"{API}/trips/{a['id']}/split", json={"at_km": 3, "at_ts": "2026-11-02T12:25:00Z"})
    assert bad.status_code == 422

    merged = client.post(f"{API}/trips/merge", json={"ids": [b["id"], a["id"]]})
    assert merged.status_code == 200, merged.text
    merged = merged.json()
    assert merged["distance_km"] == 6.3 and merged["battery_used_pct"] == pytest.approx(11.5)
    assert merged["kind"] == "round_trip" and merged["origin"] == {"merged_from": [a["id"], b["id"]]}
    assert merged["costing"]["cost"] == 1.16


def test_merge_needs_adjacent_trips(client, lynk):
    for hour in (8, 10, 12):
        send(client, event("trip.recorded", trip_payload(start_ts=f"2026-11-03T{hour:02}:00:00Z",
                                                          end_ts=f"2026-11-03T{hour:02}:30:00Z"), lynk["id"]))
    first, _middle, last = sorted(trips(client), key=lambda t: t["start_ts"])
    response = client.post(f"{API}/trips/merge", json={"ids": [first["id"], last["id"]]})
    assert response.status_code == 422


def test_manual_trip_and_idle(client, lynk):
    response = client.post(f"{API}/trips", json={
        "vehicle_id": lynk["id"], "start_ts": "2026-11-04T08:00:00+01:00", "end_ts": "2026-11-04T08:40:00+01:00",
        "distance_km": 30, "battery_start_pct": 90, "battery_end_pct": 60,
    })
    assert response.status_code == 201, response.text
    assert response.json()["battery_used_pct"] == 30
    send(client, event("idle.recorded", {"start_ts": "2026-11-04T09:00:00Z", "end_ts": "2026-11-04T17:00:00Z",
                                         "battery_start_pct": 60, "battery_end_pct": 58}, lynk["id"]))
    [idle] = client.get(f"{API}/idle-records").json()["items"]
    assert idle["costing"]["energy_kwh"] == pytest.approx(0.33)
    period = client.get(f"{API}/summary", params={"from": "2026-11-01", "to": "2026-11-30"}).json()
    assert period["vehicles"][0]["period"]["idle_kwh"] == pytest.approx(0.33)
