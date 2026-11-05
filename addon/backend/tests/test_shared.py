"""Costs shared by several vehicles (docs/costs.md#shared-costs)."""

from datetime import date

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from autoledger.ledger import ExpenseData, expense_in_range, split_shares
from autoledger.migrate import alembic_config

API = "/api/v1"
TODAY = date(2026, 11, 5)
OCT, NOV = date(2026, 10, 1), date(2026, 11, 1)


# --- Ledger -------------------------------------------------------------------


def test_equal_split_follows_the_vehicles_taking_part():
    members = {"a": (date(2026, 1, 1), None), "b": (date(2026, 1, 1), date(2026, 9, 20)),
               "c": (date(2026, 10, 15), None)}
    months = [date(2026, 9, 1), OCT, NOV]
    # September: a and b; October: a and c (b sold in September, c bought halfway through October).
    assert split_shares("equal", months, "a", members) == {date(2026, 9, 1): 0.5, OCT: 0.5, NOV: 0.5}
    assert split_shares("equal", months, "b", members) == {date(2026, 9, 1): 0.5}
    assert split_shares("equal", months, "c", members) == {OCT: 0.5, NOV: 0.5}


def test_percent_split_is_scaled_to_the_vehicles_taking_part():
    members = {"a": (date(2026, 1, 1), None), "b": (date(2026, 1, 1), date(2026, 9, 30))}
    shares = split_shares("percent", [date(2026, 9, 1), OCT], "a", members, percents={"a": 60, "b": 40})
    assert shares == {date(2026, 9, 1): 0.6, OCT: 1.0}


def test_km_split_uses_the_distance_of_each_month():
    members = {"a": (date(2026, 1, 1), None), "b": (date(2026, 1, 1), None)}
    driven = {("a", OCT): 300, ("b", OCT): 100, ("a", NOV): 0, ("b", NOV): 0}

    def km(vehicle, start, end):
        return driven[(vehicle, start)]

    assert split_shares("km", [OCT, NOV], "a", members, km=km) == {OCT: 0.75, NOV: 0.5}  # nobody drove: equal


def test_one_off_km_split_looks_at_the_year_before():
    members = {"a": (date(2025, 1, 1), None), "b": (date(2025, 1, 1), None)}
    seen = []

    def km(vehicle, start, end):
        seen.append((start, end))
        return 900 if vehicle == "a" else 100

    assert split_shares("km", [OCT], "a", members, km=km) == {OCT: 0.9}
    assert seen[0] == (date(2025, 11, 1), NOV)


def test_shared_expense_counts_with_its_share():
    yearly = ExpenseData(date(2026, 1, 1), 120, "yearly", shares={OCT: 0.25})
    assert expense_in_range(yearly, OCT, NOV, TODAY) == pytest.approx(2.5)
    assert expense_in_range(yearly, date(2026, 9, 1), OCT, TODAY) == 0  # no share in September
    once = ExpenseData(date(2026, 10, 10), 80, shares={OCT: 0.5})
    assert expense_in_range(once, OCT, NOV, TODAY) == 40


# --- API ----------------------------------------------------------------------


@pytest.fixture
def lynk(client):
    response = client.post(f"{API}/vehicles", json={
        "name": "Lynk & Co 01", "type": "PHEV", "fuel_type": "petrol", "start_odometer_km": 20000,
        "start_date": "2026-09-01",
    })
    assert response.status_code == 201, response.text
    return response.json()


def shared(client, vehicles, split="equal", **body):
    payload = {"category": "subscription", "amount": 120, "date": "2026-09-01", "recurrence": "yearly",
               "split": split, "split_vehicles": vehicles, **body}
    return client.post(f"{API}/expenses", json=payload)


def other_cost(client, vehicle, start="2026-09-01", end="2026-10-31"):
    report = client.get(f"{API}/reports/period", params={"from": start, "to": end}).json()
    if vehicle is None:
        return report["combined"]["total"]["other_cost"]
    return next(v for v in report["vehicles"] if v["vehicle"]["id"] == vehicle["id"])["total"]["other_cost"]


def test_shared_cost_is_split_equally(client, vw_up, lynk):
    response = shared(client, [{"vehicle_id": vw_up["id"]}, {"vehicle_id": lynk["id"]}])
    assert response.status_code == 201, response.text
    expense = response.json()
    assert expense["vehicle_id"] is None
    assert expense["split_vehicles"] == [{"vehicle_id": vw_up["id"], "percent": None},
                                         {"vehicle_id": lynk["id"], "percent": None}]
    # 120 a year is 10 a month; two months, half each.
    assert other_cost(client, vw_up) == 10
    assert other_cost(client, lynk) == 10
    assert other_cost(client, None) == 20
    # Both vehicles' lists show it, and so do their exports.
    for vehicle in (vw_up, lynk):
        ids = [e["id"] for e in client.get(f"{API}/expenses", params={"vehicle_id": vehicle["id"]}).json()["items"]]
        assert ids == [expense["id"]]
    csv_text = client.get(f"{API}/export/expenses.csv", params={"vehicle_id": lynk["id"]}).text
    assert "VW Up; Lynk & Co 01" in csv_text


def test_shared_cost_by_percent_and_back_to_one_vehicle(client, vw_up, lynk):
    expense = shared(client, [{"vehicle_id": vw_up["id"], "percent": 25}, {"vehicle_id": lynk["id"], "percent": 75}],
                     split="percent").json()
    assert other_cost(client, vw_up) == 5 and other_cost(client, lynk) == 15

    # Changing to "by km" drops the percentages; without any km driven it is split equally.
    response = client.patch(f"{API}/expenses/{expense['id']}", json={"split": "km"})
    assert response.status_code == 200, response.text
    assert all(s["percent"] is None for s in response.json()["split_vehicles"])
    assert other_cost(client, vw_up) == 10

    # A cost of one vehicle again: the list of vehicles is cleared.
    response = client.patch(f"{API}/expenses/{expense['id']}", json={"split": None, "vehicle_id": lynk["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["split_vehicles"] == []
    assert other_cost(client, vw_up) == 0 and other_cost(client, lynk) == 20


def test_shared_cost_by_km(client, vw_up, lynk):
    for vehicle, start, end in ((vw_up, 41000, 41300), (lynk, 20000, 20100)):
        client.post(f"{API}/odometer-readings", json={"vehicle_id": vehicle["id"], "ts": "2026-10-01T00:00:00+02:00",
                                                       "odometer_km": start})
        client.post(f"{API}/odometer-readings", json={"vehicle_id": vehicle["id"], "ts": "2026-11-01T00:00:00+01:00",
                                                       "odometer_km": end})
    shared(client, [{"vehicle_id": vw_up["id"]}, {"vehicle_id": lynk["id"]}], split="km")
    # October: 300 and 100 km, so 7.50 and 2.50 of the 10.
    assert other_cost(client, vw_up, "2026-10-01", "2026-10-31") == 7.5
    assert other_cost(client, lynk, "2026-10-01", "2026-10-31") == 2.5


def test_shared_cost_validation(client, vw_up, lynk):
    nl = {"Accept-Language": "nl"}
    one = shared(client, [{"vehicle_id": vw_up["id"]}])
    assert one.status_code == 422 and "at least two vehicles" in one.text
    response = client.post(f"{API}/expenses", headers=nl, json={
        "category": "other", "amount": 10, "date": "2026-10-01", "split": "equal",
        "split_vehicles": [{"vehicle_id": vw_up["id"]}, {"vehicle_id": vw_up["id"]}]})
    assert "Kies minstens twee voertuigen" in response.json()["error"]["message"]
    percent = shared(client, [{"vehicle_id": vw_up["id"], "percent": 50}, {"vehicle_id": lynk["id"], "percent": 40}],
                     split="percent")
    assert percent.status_code == 422 and "add up to 100" in percent.text
    unknown = shared(client, [{"vehicle_id": vw_up["id"]}, {"vehicle_id": "nope"}])
    assert unknown.status_code == 422 and "Unknown vehicle" in unknown.text
    single = client.post(f"{API}/expenses", json={"category": "other", "amount": 10, "date": "2026-10-01"})
    assert single.status_code == 422 and "Choose a vehicle" in single.text


def test_migration_keeps_existing_expenses(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    command.upgrade(alembic_config(url), "0006")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO vehicles (id, name, type, fuel_type, tracking, start_odometer_km, start_date, created_at, "
            "updated_at, version, depreciation_enabled) VALUES ('v1', 'Up', 'ICE', 'petrol', 'manual', 0, "
            "'2026-01-01', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', 1, 0)"))
        conn.execute(text(
            "INSERT INTO expenses (id, vehicle_id, category, amount, date, created_at, updated_at, version) VALUES "
            "('e1', 'v1', 'insurance', 600, '2026-01-01', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', 1)"))
    command.upgrade(alembic_config(url), "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT vehicle_id, split, split_vehicles, amount FROM expenses")).one()
    assert tuple(row) == ("v1", None, "[]", 600)
    engine.dispose()
