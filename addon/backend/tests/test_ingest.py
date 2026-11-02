import uuid

import pytest

API = "/api/v1"


@pytest.fixture
def lynk(client):
    response = client.post(
        f"{API}/vehicles",
        json={
            "name": "Lynk & Co 01",
            "type": "PHEV",
            "fuel_type": "petrol",
            "tank_l": 51,
            "battery_usable_kwh": 14.1,
            "kwh_per_pct": 0.165,
            "start_odometer_km": 63000,
            "start_date": "2026-10-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def event(type_, payload, vehicle_id=None, occurred_at="2026-11-02T12:00:00Z", uid=None):
    return {
        "uuid": uid or str(uuid.uuid4()),
        "type": type_,
        "vehicle_id": vehicle_id,
        "occurred_at": occurred_at,
        "payload": payload,
    }


def send(client, *events):
    response = client.post(f"{API}/ingest", json={"events": list(events)})
    assert response.status_code == 200, response.text
    return response.json()


def charge_payload(**overrides):
    payload = {
        "session_id": "shelly-1",
        "charger_key": "sub-charger",
        "charger_name": "Shelly EV charger",
        "start_ts": "2026-11-01T22:00:00Z",
        "energy_kwh": 2.0,
        "cost": 0.38,
    }
    return {**payload, **overrides}


def open_reviews(client):
    return client.get(f"{API}/review-items").json()["items"]


# --- Home charging --------------------------------------------------------


def test_home_charge_lifecycle(client, lynk):
    vid = lynk["id"]
    send(client, event("charge.started", charge_payload(energy_kwh=0, cost=0), vid))
    send(client, event("charge.updated", charge_payload(energy_kwh=6.0, cost=1.14), vid))
    charges = client.get(f"{API}/charges").json()["items"]
    assert len(charges) == 1 and charges[0]["is_open"] is True and charges[0]["cost"] == 1.14

    samples = [{"ts": "2026-11-01T23:00:00Z", "kwh": 16.5, "price": 0.19}]
    send(
        client,
        event(
            "charge.completed",
            charge_payload(energy_kwh=16.5, cost=3.135, end_ts="2026-11-02T05:00:00Z", price_samples=samples),
            vid,
        ),
    )
    charge = client.get(f"{API}/charges").json()["items"][0]
    assert charge["is_open"] is False
    assert charge["kind"] == "home" and charge["price_mode"] == "samples"
    assert charge["energy_kwh"] == 16.5 and charge["cost"] == pytest.approx(3.135)
    assert charge["avg_price"] == pytest.approx(0.19)

    # A late progress event must not reopen the finished session.
    send(client, event("charge.updated", charge_payload(energy_kwh=10.0, cost=2.0), vid))
    charge = client.get(f"{API}/charges").json()["items"][0]
    assert charge["is_open"] is False and charge["energy_kwh"] == 16.5

    summary = client.get(f"{API}/summary", params={"from": "2026-11-01", "to": "2026-11-30"}).json()
    period = summary["vehicles"][0]["period"]
    assert period["electricity_kwh"] == 16.5
    assert period["electricity_cost"] == pytest.approx(3.135, abs=0.006)
    assert summary["vehicles"][0]["last_charge"]["energy_kwh"] == 16.5


def test_duplicate_events_are_ignored(client, lynk):
    e = event("charge.started", charge_payload(), lynk["id"])
    assert len(send(client, e)["accepted"]) == 1
    result = send(client, e)
    assert result["duplicates"] == [e["uuid"]] and not result["accepted"]


def test_user_price_survives_collector_updates(client, lynk):
    vid = lynk["id"]
    send(client, event("charge.started", charge_payload(energy_kwh=1.0), vid))
    charge = client.get(f"{API}/charges").json()["items"][0]
    edited = client.patch(f"{API}/charges/{charge['id']}", json={"price_mode": "per_kwh", "price_per_kwh": 0.10})
    assert edited.status_code == 200, edited.text
    assert "price_mode" in edited.json()["locked_fields"]

    send(client, event("charge.completed", charge_payload(energy_kwh=12.0, cost=2.28), vid))
    charge = client.get(f"{API}/charges").json()["items"][0]
    assert charge["energy_kwh"] == 12.0
    assert charge["price_mode"] == "per_kwh"
    assert charge["cost"] == pytest.approx(1.2)
    assert charge["auto_cost"] == pytest.approx(2.28)


def test_charge_without_vehicle_goes_to_review(client, lynk):
    send(client, event("charge.completed", charge_payload(end_ts="2026-11-02T05:00:00Z")))
    [item] = open_reviews(client)
    assert item["reason"] == "charge_without_vehicle"
    assert item["record"]["energy_kwh"] == 2.0

    resolved = client.post(
        f"{API}/review-items/{item['id']}/resolve", json={"action": "update", "values": {"vehicle_id": lynk["id"]}}
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["record"]["vehicle_id"] == lynk["id"]
    assert open_reviews(client) == []


# --- Public charging and refuels ------------------------------------------


def test_external_charge_uses_default_public_price(client, lynk):
    payload = {
        "window_start": "2026-11-01T09:00:00Z",
        "window_end": "2026-11-01T13:00:00Z",
        "place": {"lat": 52.07, "lon": 4.3, "address": "Fastned Den Haag"},
        "battery_start_pct": 30,
        "battery_end_pct": 80,
        "energy_kwh_estimated": 8.25,
        "car_reported_charging": True,
    }
    send(client, event("external_charge.detected", payload, lynk["id"]))
    [item] = open_reviews(client)
    assert item["reason"] == "public_charge_price"
    charge = item["record"]
    assert charge["kind"] == "public" and charge["energy_estimated"] is True
    assert charge["cost"] == pytest.approx(8.25 * 0.59)

    client.post(
        f"{API}/review-items/{item['id']}/resolve",
        json={"action": "update", "values": {"price_mode": "total", "price_total": 4.50, "energy_kwh": 8.0}},
    )
    charge = client.get(f"{API}/charges/{charge['id']}").json()
    assert charge["cost"] == 4.5 and charge["status"] == "ok"


def test_refuel_detection_and_confirmation_by_edit(client, lynk):
    vid = lynk["id"]
    client.post(
        f"{API}/refuels",
        json={"vehicle_id": vid, "ts": "2026-10-15T12:00:00+02:00", "litres": 30, "price_per_l": 2.03},
    )
    payload = {
        "ts": "2026-11-02T12:42:56Z",
        "place": {"address": "Shell Voorburg"},
        "odometer_km": 63445,
        "fuel_start_l": 16.0,
        "fuel_end_l": 50.0,
        "litres_estimated": 34.0,
    }
    send(client, event("refuel.detected", payload, vid))
    [item] = open_reviews(client)
    refuel = item["record"]
    assert item["reason"] == "refuel_price"
    assert refuel["price_per_l"] == 2.03 and refuel["status"] == "needs_review"
    assert refuel["full_tank"] is True and refuel["station"] == "Shell Voorburg"

    # Correcting the total on the Fuel page confirms it and closes the review item.
    patched = client.patch(f"{API}/refuels/{refuel['id']}", json={"total": 70.38}).json()
    assert patched["status"] == "ok" and patched["price_per_l"] == pytest.approx(2.07)
    assert open_reviews(client) == []


def test_review_delete_action(client, lynk):
    payload = {"ts": "2026-11-02T12:00:00Z", "fuel_start_l": 10, "fuel_end_l": 14, "litres_estimated": 4}
    send(client, event("refuel.detected", payload, lynk["id"]))
    [item] = open_reviews(client)
    client.post(f"{API}/review-items/{item['id']}/resolve", json={"action": "delete"})
    assert client.get(f"{API}/refuels").json()["total"] == 0
    again = client.post(f"{API}/review-items/{item['id']}/resolve", json={"action": "dismiss"})
    assert again.status_code == 409


# --- Odometer and errors --------------------------------------------------


def test_odometer_readings_feed_distance(client, lynk):
    vid = lynk["id"]
    e = event("odometer.reading", {"ts": "2026-10-31T00:00:00+01:00", "odometer_km": 63300}, vid)
    send(client, e, event("odometer.reading", {"ts": "2026-10-31T00:00:00+01:00", "odometer_km": 63300}, vid))
    assert client.get(f"{API}/odometer-readings").json()["total"] == 1
    october = client.get(f"{API}/summary", params={"from": "2026-10-01", "to": "2026-10-31"}).json()
    assert october["vehicles"][0]["period"]["km"] == 300


def test_bad_events_are_rejected_but_not_lost(client, lynk):
    result = send(
        client,
        event("trip.recorded", {}, lynk["id"]),
        event("refuel.detected", {"ts": "2026-11-02T12:00:00Z"}, lynk["id"]),
        event("odometer.reading", {"ts": "2026-11-02T12:00:00Z", "odometer_km": 63445}, "unknown-vehicle"),
        event("odometer.reading", {"ts": "2026-11-02T12:00:00Z", "odometer_km": 63445}, lynk["id"]),
    )
    assert len(result["rejected"]) == 3 and len(result["accepted"]) == 1
    reasons = [i["reason"] for i in open_reviews(client)]
    assert reasons == ["rejected_event"] * 3
    summary = client.get(f"{API}/summary").json()
    assert summary["review_count"] == 3
    assert client.get(f"{API}/info").json()["last_ingest_at"] is not None


# --- Manual charges -------------------------------------------------------


def test_manual_public_charge_validation(client, lynk):
    base = {"vehicle_id": lynk["id"], "kind": "public", "start_ts": "2026-11-01T10:00:00+01:00", "energy_kwh": 10}
    assert client.post(f"{API}/charges", json=base).status_code == 422  # per_kwh needs a price
    created = client.post(f"{API}/charges", json={**base, "price_per_kwh": 0.49, "session_fee": 0.35}).json()
    assert created["cost"] == pytest.approx(5.25)
    free = client.patch(f"{API}/charges/{created['id']}", json={"price_mode": "free"}).json()
    assert free["cost"] == 0
    no_vehicle = client.post(f"{API}/charges", json={**base, "vehicle_id": None, "price_per_kwh": 0.5})
    assert no_vehicle.status_code == 422
