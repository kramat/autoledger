import pytest
from fastapi.testclient import TestClient

from autoledger.main import create_app

from .conftest import make_config

API = "/api/v1"


# --- Access ---------------------------------------------------------------


def test_requests_without_token_are_rejected(app):
    with TestClient(app) as anonymous:
        assert anonymous.get(f"{API}/health").status_code == 200
        response = anonymous.get(f"{API}/vehicles")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_token_cannot_be_read_with_the_token(client):
    assert client.get(f"{API}/settings/token").status_code == 403


def test_trusted_caller_can_manage_token(tmp_path):
    app = create_app(make_config(tmp_path, dev=True))
    with TestClient(app) as trusted:
        old = trusted.get(f"{API}/settings/token").json()["token"]
        new = trusted.post(f"{API}/settings/token/regenerate").json()["token"]
        assert old != new
        assert app.state.token == new


def test_restart_keeps_data_and_token(tmp_path, vw_up, app):
    again = create_app(make_config(tmp_path))
    assert again.state.token == app.state.token
    with TestClient(again, headers={"Authorization": f"Bearer {again.state.token}"}) as c:
        assert c.get(f"{API}/vehicles").json()["total"] == 1
    assert not (tmp_path / "backups").exists()  # already at head, no backup needed


# --- Vehicles -------------------------------------------------------------


def test_vehicle_validation_error_format(client):
    response = client.post(
        f"{API}/vehicles",
        json={"name": "X", "fuel_type": "none", "start_odometer_km": 0, "start_date": "2026-01-01"},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "fuel type" in error["message"]


def test_vehicle_archive_and_unknown_fields(client, vw_up):
    url = f"{API}/vehicles/{vw_up['id']}"
    archived = client.patch(url, json={"archived": True}).json()
    assert archived["archived_at"] is not None
    assert archived["version"] == 2
    assert client.patch(url, json={"colour": "red"}).status_code == 422


def test_if_match_conflict(client, vw_up):
    url = f"{API}/vehicles/{vw_up['id']}"
    assert client.patch(url, json={"plate": "AB-123-C"}, headers={"If-Match": "1"}).status_code == 200
    response = client.patch(url, json={"plate": "XX"}, headers={"If-Match": "1"})
    assert response.status_code == 409


# --- Refuels --------------------------------------------------------------


def add_refuel(client, vehicle_id, **fields):
    response = client.post(f"{API}/refuels", json={"vehicle_id": vehicle_id, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_refuel_derives_the_missing_value(client, vw_up):
    refuel = add_refuel(client, vw_up["id"], ts="2026-10-01T10:00:00+02:00", litres=30, total=61.5)
    assert refuel["price_per_l"] == pytest.approx(2.05)
    assert refuel["ts"].startswith("2026-10-01T08:00:00")  # stored in UTC


def test_refuel_needs_two_values_and_consistency(client, vw_up):
    base = {"vehicle_id": vw_up["id"], "ts": "2026-10-01T10:00:00+02:00"}
    assert client.post(f"{API}/refuels", json={**base, "litres": 30}).status_code == 422
    inconsistent = client.post(
        f"{API}/refuels", json={**base, "litres": 30, "price_per_l": 2, "total": 70}
    )
    assert inconsistent.status_code == 422


def test_refuel_needs_timezone(client, vw_up):
    response = client.post(
        f"{API}/refuels", json={"vehicle_id": vw_up["id"], "ts": "2026-10-01T10:00:00", "litres": 30, "total": 60}
    )
    assert response.status_code == 422


def test_refuel_patch_recalculates_untouched_value(client, vw_up):
    refuel = add_refuel(client, vw_up["id"], ts="2026-10-01T10:00:00+02:00", litres=30, price_per_l=2.0)
    url = f"{API}/refuels/{refuel['id']}"
    patched = client.patch(url, json={"total": 63}).json()
    assert patched["litres"] == 30
    assert patched["price_per_l"] == pytest.approx(2.1)
    patched = client.patch(url, json={"litres": 31}).json()
    assert patched["total"] == pytest.approx(65.1)


def test_unknown_vehicle(client):
    response = client.post(
        f"{API}/refuels",
        json={"vehicle_id": "nope", "ts": "2026-10-01T10:00:00+02:00", "litres": 30, "total": 60},
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"vehicle_id": "Unknown vehicle"}


def test_soft_delete_and_restore(client, vw_up):
    refuel = add_refuel(client, vw_up["id"], ts="2026-10-01T10:00:00+02:00", litres=30, total=60)
    url = f"{API}/refuels/{refuel['id']}"
    assert client.delete(url).status_code == 204
    assert client.get(f"{API}/refuels").json()["total"] == 0
    assert client.get(f"{API}/refuels", params={"include_deleted": True}).json()["total"] == 1
    assert client.post(f"{url}/restore").json()["deleted_at"] is None
    assert client.get(f"{API}/refuels").json()["total"] == 1


def test_refuel_list_has_consumption_and_date_filter(client, vw_up):
    vid = vw_up["id"]
    add_refuel(client, vid, ts="2026-09-01T09:00:00+02:00", litres=30, total=60, odometer_km=41000)
    add_refuel(client, vid, ts="2026-10-01T09:00:00+02:00", litres=33, total=66, odometer_km=41600)
    items = client.get(f"{API}/refuels", params={"vehicle_id": vid}).json()["items"]
    assert [i["l_per_100km"] for i in items] == [5.5, None]  # newest first
    october = client.get(f"{API}/refuels", params={"from": "2026-10-01", "to": "2026-10-31"}).json()
    assert october["total"] == 1


# --- Summary and export ---------------------------------------------------


def test_summary_for_manual_vehicle(client, vw_up):
    vid = vw_up["id"]
    add_refuel(client, vid, ts="2026-09-01T00:00:00+02:00", litres=30, total=60, odometer_km=41000)
    add_refuel(client, vid, ts="2026-10-01T00:00:00+02:00", litres=33, total=66, odometer_km=41600)
    client.post(
        f"{API}/maintenance",
        json={"vehicle_id": vid, "date": "2026-09-20", "category": "service", "description": "Oil", "cost": 180},
    )
    client.post(
        f"{API}/expenses",
        json={"vehicle_id": vid, "category": "insurance", "amount": 360, "date": "2026-01-01", "recurrence": "yearly"},
    )

    data = client.get(f"{API}/summary", params={"from": "2026-09-01", "to": "2026-09-30"}).json()
    assert data["currency"] == "EUR"
    september = data["vehicles"][0]["period"]
    assert september["km"] == 600
    assert september["fuel_cost"] == 60
    assert september["maintenance_cost"] == 180
    assert september["other_cost"] == 30
    assert september["total_cost"] == 270
    assert september["total_cost_per_km"] == 0.45
    assert data["vehicles"][0]["odometer_km"] == 41600
    assert data["combined"]["period"]["total_cost"] == 270
    assert data["vehicles"][0]["monthly"][-1]["month"] == "2026-09"

    october = client.get(f"{API}/summary", params={"from": "2026-10-01", "to": "2026-10-31"}).json()
    assert october["vehicles"][0]["period"]["fuel_l_per_100km"] == 5.5


def test_summary_rejects_reversed_range(client):
    assert client.get(f"{API}/summary", params={"from": "2026-10-02", "to": "2026-10-01"}).status_code == 400


def test_csv_export(client, vw_up):
    add_refuel(client, vw_up["id"], ts="2026-10-01T10:00:00+02:00", litres=30, total=60, station="Shell")
    response = client.get(f"{API}/export/refuels.csv")
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("vehicle_id,vehicle,ts")
    assert "VW Up" in lines[1] and "2026-10-01T10:00:00+02:00" in lines[1]
    assert client.get(f"{API}/export/nothing.csv").status_code == 404


def test_settings_roundtrip(client):
    settings = client.get(f"{API}/settings").json()
    assert settings["fuel_prices"]["petrol"] == 2.0
    settings["electricity_price"] = 0.19
    assert client.put(f"{API}/settings", json=settings).json()["electricity_price"] == 0.19
    assert client.get(f"{API}/settings").json()["electricity_price"] == 0.19
