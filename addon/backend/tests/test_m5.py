"""M5: depreciation and attachments."""

from datetime import date

from fastapi.testclient import TestClient

from autoledger.ledger import DepreciationData, depreciation_in_range
from autoledger.main import create_app

from .conftest import make_config

API = "/api/v1"
TODAY = date(2026, 11, 3)
# A JPEG header is enough: the add-on stores bytes, it does not decode images.
PHOTO = b"\xff\xd8\xff\xe0" + b"receipt" * 100


# --- Depreciation -----------------------------------------------------------

LYNK = DepreciationData(purchase_date=date(2024, 1, 1), resale_date=date(2029, 1, 1), amount=30000)


def test_depreciation_is_the_same_every_month():
    # 30 000 over 60 months: 500 per month, also in short months.
    assert depreciation_in_range(LYNK, date(2026, 2, 1), date(2026, 3, 1), TODAY) == 500
    assert round(depreciation_in_range(LYNK, date(2026, 1, 1), date(2027, 1, 1), date(2027, 6, 1)), 6) == 6000
    # Half of September is half a month.
    assert depreciation_in_range(LYNK, date(2026, 9, 16), date(2026, 10, 1), TODAY) == 250


def test_depreciation_adds_up_and_stops_at_today_and_resale():
    whole = depreciation_in_range(LYNK, date(2020, 1, 1), date(2035, 1, 1), date(2035, 1, 1))
    assert round(whole, 6) == 30000
    # Only the days that have happened: 1–3 November is 3/30 of a month.
    assert depreciation_in_range(LYNK, date(2026, 11, 1), date(2026, 12, 1), TODAY) == 50
    assert depreciation_in_range(LYNK, date(2029, 1, 1), date(2030, 1, 1), date(2030, 1, 1)) == 0


def test_depreciation_starts_with_tracking():
    # Bought in 2024, tracked in AutoLedger from 1 Oct 2026: the same 500 per month, from October on.
    tracked = DepreciationData(LYNK.purchase_date, LYNK.resale_date, LYNK.amount, count_from=date(2026, 10, 1))
    assert depreciation_in_range(tracked, date(2026, 1, 1), date(2026, 11, 1), TODAY) == 500


def test_depreciation_with_partial_first_month():
    car = DepreciationData(purchase_date=date(2026, 1, 16), resale_date=date(2026, 3, 16), amount=1000)
    # 16 Jan – 16 Mar is 16/31 + 1 + 15/31 = 2 months: 500 per month.
    assert round(depreciation_in_range(car, date(2026, 2, 1), date(2026, 3, 1), TODAY), 6) == 500
    assert round(depreciation_in_range(car, date(2026, 1, 1), date(2027, 1, 1), TODAY), 6) == 1000


def test_vehicle_depreciation_in_totals(client, vw_up):
    url = f"{API}/vehicles/{vw_up['id']}"
    # Switching it on needs the purchase and resale details.
    assert client.patch(url, json={"depreciation_enabled": True}).status_code == 422
    assert client.patch(url, json={"purchase_price": 9000, "purchase_date": "2024-01-01",
                                   "resale_estimate": 12000, "resale_date": "2029-01-01",
                                   "depreciation_enabled": True}).status_code == 422
    assert client.patch(url, json={"purchase_price": 9000, "purchase_date": "2024-01-01",
                                   "resale_date": "2023-01-01"}).status_code == 422

    response = client.patch(url, json={"purchase_price": 9000, "purchase_date": "2024-01-01",
                                       "resale_estimate": 3000, "resale_date": "2029-01-01",
                                       "depreciation_enabled": True})
    assert response.status_code == 200, response.text
    report = client.get(f"{API}/reports/period", params={"from": "2026-09-01", "to": "2026-10-31",
                                                         "group": "month"}).json()
    total = report["vehicles"][0]["total"]
    assert total["depreciation_cost"] == 200  # 6 000 over 60 months, two months
    assert total["total_cost"] == 200
    assert [g["depreciation_cost"] for g in report["vehicles"][0]["groups"]] == [100, 100]

    client.patch(url, json={"depreciation_enabled": False})
    report = client.get(f"{API}/reports/period", params={"from": "2026-09-01", "to": "2026-10-31"}).json()
    assert report["vehicles"][0]["total"]["depreciation_cost"] == 0


# --- Attachments -------------------------------------------------------------


def refuel(client, vehicle_id) -> dict:
    response = client.post(f"{API}/refuels", json={"vehicle_id": vehicle_id, "ts": "2026-10-01T12:00:00+02:00",
                                                    "odometer_km": 41500, "litres": 30, "total": 60})
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, record_id, content=PHOTO, mime="image/jpeg", resource="refuels", filename="bon.jpg"):
    return client.post(f"{API}/attachments", params={"resource": resource, "record_id": record_id,
                                                     "filename": filename},
                       content=content, headers={"Content-Type": mime})


def test_attach_a_receipt_photo(client, vw_up, tmp_path):
    record = refuel(client, vw_up["id"])
    response = upload(client, record["id"])
    assert response.status_code == 201, response.text
    item = response.json()
    assert (item["filename"], item["mime_type"], item["size"]) == ("bon.jpg", "image/jpeg", len(PHOTO))
    assert (tmp_path / "attachments" / item["id"]).read_bytes() == PHOTO

    listed = client.get(f"{API}/refuels").json()["items"][0]
    assert [a["id"] for a in listed["attachments"]] == [item["id"]]
    file = client.get(f"{API}/attachments/{item['id']}/file")
    assert file.status_code == 200 and file.content == PHOTO
    assert file.headers["content-type"] == "image/jpeg" and file.headers["x-content-type-options"] == "nosniff"
    assert file.headers["content-disposition"].startswith("inline")

    # Deleting can be undone.
    assert client.delete(f"{API}/attachments/{item['id']}").status_code == 204
    assert client.get(f"{API}/attachments", params={"resource": "refuels", "record_id": record["id"]}).json() == []
    assert client.post(f"{API}/attachments/{item['id']}/restore").status_code == 200
    assert len(client.get(f"{API}/refuels").json()["items"][0]["attachments"]) == 1


def test_attachment_checks(client, vw_up):
    record = refuel(client, vw_up["id"])
    assert upload(client, record["id"], b"<svg onload=alert(1)>", "image/svg+xml").status_code == 415
    assert upload(client, record["id"], b"", "image/jpeg").status_code == 422
    assert upload(client, "nope").status_code == 404
    assert upload(client, record["id"], resource="trips").status_code == 422
    assert upload(client, record["id"], b"%PDF-1.7", "application/pdf", filename="../factuur.pdf").json()[
        "filename"] == "factuur.pdf"


def test_backup_with_attachments(client, vw_up, tmp_path):
    record = refuel(client, vw_up["id"])
    item = upload(client, record["id"]).json()

    small = client.get(f"{API}/backup").json()
    assert "files" not in small and len(small["tables"]["attachments"]) == 1
    full = client.get(f"{API}/backup", params={"attachments": "true"}).json()
    assert list(full["files"]) == [item["id"]]

    fresh = create_app(make_config(tmp_path / "other"))
    with TestClient(fresh, headers={"Authorization": f"Bearer {fresh.state.token}"}) as other:
        result = other.post(f"{API}/restore", json=full).json()
        assert result["files"] == {"written": 1, "skipped": 0}
        assert other.get(f"{API}/attachments/{item['id']}/file").content == PHOTO

    # Without files, the row is restored and its file reported as missing.
    bare = create_app(make_config(tmp_path / "bare"))
    with TestClient(bare, headers={"Authorization": f"Bearer {bare.state.token}"}) as other:
        assert other.post(f"{API}/restore", json=small).json()["files"] == {"written": 0, "skipped": 0}
        assert other.get(f"{API}/attachments/{item['id']}/file").status_code == 404
