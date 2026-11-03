"""M4: maintenance schedules, reports, XLSX export, backup/restore and CSV import."""

import io
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from autoledger.importer import guess_date_order, guess_decimal, guess_mapping, parse_number, read_csv
from autoledger.main import create_app
from autoledger.maintenance import DoneData, ScheduleData, add_months_exact, due, next_due

from .conftest import make_config
from .test_ingest import event, send

API = "/api/v1"
TODAY = date(2026, 11, 3)


# --- Due logic --------------------------------------------------------------


def schedule(**overrides) -> ScheduleData:
    values = {"id": "s1", "name": "Service", "category": "service", "interval_months": 12, "interval_km": 15000,
              "last_done_date": date(2026, 1, 15), "last_done_km": 30000}
    return ScheduleData(**{**values, **overrides})


def test_add_months_keeps_the_day_or_clamps_it():
    assert add_months_exact(date(2026, 1, 15), 12) == date(2027, 1, 15)
    assert add_months_exact(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_due_by_date_when_driving_little():
    result = due(schedule(), [], TODAY, odometer_km=36000, odometer_date=TODAY, km_per_day=20)
    # 9 000 km left at 20 km/day is 450 days: the date (15 Jan 2027) comes first.
    assert result.due_date == date(2027, 1, 15)
    assert result.due_km == 45000 and result.km_left == 9000
    assert (result.estimated_date, result.reason, result.days_left) == (date(2027, 1, 15), "date", 73)
    assert result.status == "ok"


def test_due_by_km_when_driving_a_lot():
    result = due(schedule(), [], TODAY, odometer_km=44500, odometer_date=TODAY, km_per_day=50)
    assert result.reason == "km" and result.km_left == 500
    assert result.estimated_date == TODAY + timedelta(days=10)
    assert result.status == "soon"  # within 1 000 km


def test_overdue_by_date_or_km():
    assert due(schedule(last_done_date=date(2025, 10, 1)), [], TODAY, 31000, TODAY, 10).status == "overdue"
    assert due(schedule(), [], TODAY, 45200, TODAY, 10).status == "overdue"


def test_soon_by_reminder_days():
    result = due(schedule(last_done_date=date(2025, 11, 20), interval_km=None), [], TODAY)
    assert result.days_left == 17 and result.status == "soon"


def test_records_move_the_starting_point():
    linked = DoneData("m1", date(2026, 10, 1), "repair", schedule_id="s1", odometer_km=40000)
    same_category = DoneData("m2", date(2026, 6, 1), "service", odometer_km=38000)
    other_schedule = DoneData("m3", date(2026, 10, 20), "service", schedule_id="s2", odometer_km=40500)
    result = due(schedule(), [same_category, linked, other_schedule], TODAY, 41000, TODAY, 20)
    assert (result.last_done_date, result.last_done_km, result.last_record_id) == (date(2026, 10, 1), 40000, "m1")
    assert result.due_date == date(2027, 10, 1)


def test_unknown_without_a_starting_point():
    result = due(schedule(last_done_date=None, last_done_km=None), [], TODAY, 41000, TODAY, 20)
    assert result.status == "unknown"
    assert next_due([result]) is None


def test_next_due_puts_overdue_first():
    a = due(schedule(id="a"), [], TODAY, 36000, TODAY, 20)
    b = due(schedule(id="b", last_done_date=date(2025, 10, 1)), [], TODAY, 36000, TODAY, 20)
    assert next_due([a, b]).schedule_id == "b"


# --- Schedules API ----------------------------------------------------------


def add(client, resource, **body):
    response = client.post(f"{API}/{resource}", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_schedule_due_follows_maintenance_records(client, vw_up):
    today = date.today()
    done = today - timedelta(days=300)
    schedule_ = add(client, "maintenance-schedules", vehicle_id=vw_up["id"], name="APK", category="inspection",
                    interval_months=12, last_done_date=done.isoformat())
    items = client.get(f"{API}/maintenance-schedules").json()["items"]
    assert items[0]["due"]["status"] == "ok"
    assert items[0]["due"]["due_date"] == add_months_exact(done, 12).isoformat()

    # An APK logged today (category match) starts the next year.
    add(client, "maintenance", vehicle_id=vw_up["id"], date=today.isoformat(), category="inspection",
        description="APK", cost=45)
    due_ = client.get(f"{API}/maintenance-schedules/due").json()["vehicles"][0]
    assert due_["items"][0]["schedule_id"] == schedule_["id"]
    assert due_["items"][0]["last_done_date"] == today.isoformat()
    assert due_["items"][0]["due_date"] == add_months_exact(today, 12).isoformat()

    summary = client.get(f"{API}/summary").json()["vehicles"][0]
    assert summary["next_maintenance"]["name"] == "APK"
    assert summary["maintenance"][0]["status"] == "ok"


def test_schedule_needs_an_interval_and_records_the_same_vehicle(client, vw_up):
    response = client.post(f"{API}/maintenance-schedules", json={"vehicle_id": vw_up["id"], "name": "Wash"})
    assert response.status_code == 422
    other = add(client, "vehicles", name="Other", start_odometer_km=0, start_date="2026-01-01")
    schedule_ = add(client, "maintenance-schedules", vehicle_id=other["id"], name="Service", interval_months=12)
    response = client.post(f"{API}/maintenance", json={"vehicle_id": vw_up["id"], "date": "2026-10-01",
                                                       "description": "Oil", "schedule_id": schedule_["id"]})
    assert response.status_code == 422
    assert "schedule_id" in response.json()["error"]["fields"]


def test_km_schedule_uses_the_driving_rate(client, vw_up):
    today = date.today()
    # 41 000 km on the start date (1 Sep 2026 in the fixture); 3 000 km in 60 days = 50 km/day.
    client.patch(f"{API}/vehicles/{vw_up['id']}", json={"start_date": (today - timedelta(days=60)).isoformat()})
    add(client, "odometer-readings", vehicle_id=vw_up["id"], ts=f"{today.isoformat()}T08:00:00+00:00",
        odometer_km=44000)
    add(client, "maintenance-schedules", vehicle_id=vw_up["id"], name="Service", interval_km=15000,
        last_done_km=30000)
    item = client.get(f"{API}/maintenance-schedules/due").json()["vehicles"][0]
    assert 49 < item["km_per_day"] < 51  # the start counts from local midnight
    assert item["items"][0]["km_left"] == 1000
    assert item["items"][0]["estimated_date"] == (today + timedelta(days=20)).isoformat()
    assert item["items"][0]["status"] == "soon"


def test_car_service_countdown_from_the_collector(client, vw_up):
    send(client, event("service.status", {"days_to_service": 654, "distance_to_service": 28163,
                                          "odometer_km": 64000}, vw_up["id"], "2026-11-02T12:00:00Z"))
    car = client.get(f"{API}/maintenance-schedules/due").json()["vehicles"][0]["car_service"]
    assert car["due_date"] == "2028-08-17"
    assert car["due_km"] == 92163
    assert client.get(f"{API}/review-items").json()["total"] == 0


# --- Reports ----------------------------------------------------------------


def two_cars(client, vw_up):
    lynk = add(client, "vehicles", name="Lynk", type="PHEV", fuel_type="petrol", tank_l=42,
               start_odometer_km=60000, start_date="2026-01-01")
    for vehicle, km in ((vw_up, 41000), (lynk, 60000)):
        add(client, "refuels", vehicle_id=vehicle["id"], ts="2026-09-05T10:00:00+02:00", litres=30, total=60,
            odometer_km=km + 100)
        add(client, "refuels", vehicle_id=vehicle["id"], ts="2026-10-05T10:00:00+02:00", litres=20, total=40,
            odometer_km=km + 500)
    add(client, "maintenance", vehicle_id=vw_up["id"], date="2026-10-10", category="service",
        description="Service", cost=250)
    add(client, "expenses", vehicle_id=lynk["id"], category="insurance", amount=600, date="2026-01-01",
        recurrence="yearly")
    return lynk


def test_period_report_groups_add_up(client, vw_up):
    two_cars(client, vw_up)
    for group in ("month", "quarter", "year"):
        report = client.get(f"{API}/reports/period",
                            params={"from": "2026-09-01", "to": "2026-10-31", "group": group}).json()
        for item in [*report["vehicles"], report["combined"]]:
            assert round(sum(g["total_cost"] for g in item["groups"]), 2) == item["total"]["total_cost"]
    report = client.get(f"{API}/reports/period", params={"from": "2026-09-01", "to": "2026-10-31"}).json()
    assert [g["label"] for g in report["combined"]["groups"]] == ["2026-09", "2026-10"]
    vw = report["vehicles"][0]
    assert vw["total"]["fuel_cost"] == 100 and vw["total"]["maintenance_cost"] == 250
    quarter = client.get(f"{API}/reports/period", params={"from": "2026-08-15", "to": "2026-10-31",
                                                         "group": "quarter"}).json()
    assert [(g["label"], g["from"]) for g in quarter["combined"]["groups"]] == [
        ("2026-Q3", "2026-08-15"), ("2026-Q4", "2026-10-01")]


def test_compare_scales_to_a_year(client, vw_up):
    two_cars(client, vw_up)
    report = client.get(f"{API}/reports/compare", params={"from": "2026-01-01", "to": "2026-06-30"}).json()
    lynk = report["vehicles"][1]
    assert lynk["total"]["other_cost"] == 300  # half a year of insurance
    assert lynk["per_year"]["other_cost"] == round(300 * 365.25 / 181, 2)
    assert "groups" not in lynk


def test_trends_have_months_and_seasons(client, vw_up):
    two_cars(client, vw_up)
    trends = client.get(f"{API}/reports/trends", params={"vehicle_id": vw_up["id"], "months": 3}).json()
    vehicle = trends["vehicles"][0]
    assert len(vehicle["monthly"]) == 3
    assert set(vehicle["seasons"]) == {"winter", "spring", "summer", "autumn"}
    assert vehicle["seasons"]["autumn"]["km"] > 0


def test_report_export_xlsx_and_csv(client, vw_up):
    two_cars(client, vw_up)
    params = {"from": "2026-09-01", "to": "2026-10-31"}
    response = client.get(f"{API}/reports/period.xlsx", params=params)
    assert response.status_code == 200
    book = load_workbook(io.BytesIO(response.content))
    assert book.sheetnames == ["Totals", "Per month"]
    rows = list(book["Totals"].values)
    assert rows[0][:3] == ("vehicle", "period", "from")
    assert [r[0] for r in rows[1:]] == ["VW Up", "Lynk", "All vehicles"]
    csv_text = client.get(f"{API}/reports/period.csv", params=params).text
    assert csv_text.splitlines()[0].startswith("vehicle,period,from,to,km")


def test_record_export_xlsx(client, vw_up):
    two_cars(client, vw_up)
    response = client.get(f"{API}/export/refuels.xlsx")
    rows = list(load_workbook(io.BytesIO(response.content)).active.values)
    assert rows[0][:3] == ("vehicle_id", "vehicle", "ts")
    assert len(rows) == 5
    book = load_workbook(io.BytesIO(client.get(f"{API}/export/records.xlsx").content))
    assert "maintenance-schedules" in book.sheetnames and "trips" in book.sheetnames
    assert client.get(f"{API}/export/refuels.pdf").status_code == 404


# --- Backup and restore -----------------------------------------------------


def test_backup_restores_into_an_empty_add_on(client, vw_up, tmp_path):
    two_cars(client, vw_up)
    add(client, "maintenance-schedules", vehicle_id=vw_up["id"], name="APK", interval_months=12,
        last_done_date="2026-05-01")
    backup = client.get(f"{API}/backup").json()
    assert backup["format"] == "autoledger-backup" and backup["schema_revision"] == "0005"
    assert len(backup["tables"]["refuels"]) == 4

    fresh = create_app(make_config(tmp_path / "other"))
    with TestClient(fresh, headers={"Authorization": f"Bearer {fresh.state.token}"}) as other:
        response = other.post(f"{API}/restore", json=backup)
        assert response.status_code == 200, response.text
        assert response.json()["tables"]["refuels"] == {"inserted": 4, "skipped": 0}
        assert other.get(f"{API}/summary", params={"from": "2026-09-01", "to": "2026-10-31"}).json() == \
            client.get(f"{API}/summary", params={"from": "2026-09-01", "to": "2026-10-31"}).json()
        # Not again into a database with vehicles, but merge adds nothing twice.
        assert other.post(f"{API}/restore", json=backup).status_code == 409
        merged = other.post(f"{API}/restore", params={"mode": "merge"}, json=backup).json()
        assert merged["tables"]["refuels"] == {"inserted": 0, "skipped": 4}
    assert list((tmp_path / "other" / "backups").glob("autoledger-before-restore-*.db"))


def test_restore_rejects_other_files(client):
    assert client.post(f"{API}/restore", json={"hello": 1}).status_code == 422
    newer = {"format": "autoledger-backup", "format_version": 1, "schema_revision": "9999", "tables": {}}
    assert client.post(f"{API}/restore", json=newer).status_code == 422


# --- CSV import -------------------------------------------------------------

DUTCH_CSV = """﻿Datum;Kilometerstand;Liters;Prijs per liter;Totaal;Volle tank;Tankstation
03-01-2025;38.120;31,52;1,999;63,01;ja;Shell Utrecht
28-01-2025;38.655;29,10;2,049;59,63;ja;
15-02-2025;39.010;12,00;;24,00;nee;Tango
xx-02-2025;39.100;10;2;20;ja;
"""


def test_import_helpers():
    header, rows, delimiter = read_csv(DUTCH_CSV)
    assert delimiter == ";" and header[0] == "Datum" and len(rows) == 4
    mapping = guess_mapping("refuels", header)
    assert mapping == {"ts": "Datum", "odometer_km": "Kilometerstand", "litres": "Liters",
                       "price_per_l": "Prijs per liter", "total": "Totaal", "full_tank": "Volle tank",
                       "station": "Tankstation"}
    assert guess_decimal(["31,52", "1.999,00", "38.120"]) == ","
    assert parse_number("€ 1.234,50", ",") == 1234.5
    assert parse_number("1,234.50", ".") == 1234.5
    assert guess_date_order(["03-01-2025", "28-01-2025"]) == "dmy"
    assert guess_date_order(["01/28/2025"]) == "mdy"
    assert guess_date_order(["2025-01-28"]) == "ymd"


def test_csv_import_preview_then_commit(client, vw_up):
    body = {"resource": "refuels", "vehicle_id": vw_up["id"], "content": DUTCH_CSV}
    preview = client.post(f"{API}/import/csv", json=body).json()
    assert (preview["decimal"], preview["date_order"], preview["delimiter"]) == (",", "dmy", ";")
    assert preview["counts"] == {"ok": 3, "error": 1, "duplicate": 0}
    first = preview["rows"][0]["values"]
    assert first["litres"] == 31.52 and first["odometer_km"] == 38120 and first["full_tank"] is True
    assert first["ts"].startswith("2025-01-03T12:00:00")
    assert preview["rows"][2]["values"]["price_per_l"] == 2.0  # derived from litres and total
    assert "not a date" in preview["rows"][3]["error"]
    assert client.get(f"{API}/refuels").json()["total"] == 0

    result = client.post(f"{API}/import/csv", params={"commit": True}, json=body).json()
    assert result["created"] == 3
    refuels = client.get(f"{API}/refuels").json()["items"]
    assert {r["source"] for r in refuels} == {"import"}
    assert [r["full_tank"] for r in refuels] == [False, True, True]  # newest first

    again = client.post(f"{API}/import/csv", json=body).json()
    assert again["counts"] == {"ok": 0, "error": 1, "duplicate": 3}


def test_csv_import_maintenance_with_mapping(client, vw_up):
    content = "when,what,price,kind\n2025-03-01,Big service,\"1,234.50\",Onderhoud\n2025-04-02,APK,45,APK\n"
    body = {"resource": "maintenance", "vehicle_id": vw_up["id"], "content": content,
            "mapping": {"date": "when", "description": "what", "cost": "price", "category": "kind"}}
    result = client.post(f"{API}/import/csv", params={"commit": True}, json=body).json()
    assert result["counts"]["ok"] == 2, result
    records = client.get(f"{API}/maintenance").json()["items"]
    assert [(r["category"], r["cost"]) for r in records] == [("inspection", 45), ("service", 1234.5)]


def test_csv_import_needs_a_known_vehicle(client):
    body = {"resource": "expenses", "vehicle_id": "nope", "content": "date,amount\n2025-01-01,5\n"}
    assert client.post(f"{API}/import/csv", json=body).status_code == 422


def test_backup_is_valid_json_file(client, vw_up):
    response = client.get(f"{API}/backup")
    assert response.headers["content-disposition"].startswith('attachment; filename="autoledger-backup-')
    assert json.loads(response.content)["tables"]["vehicles"][0]["name"] == "VW Up"
