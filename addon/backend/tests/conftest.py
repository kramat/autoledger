from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from autoledger.config import Config
from autoledger.main import create_app

TZ = ZoneInfo("Europe/Amsterdam")


def make_config(data_dir: Path, *, dev: bool = False) -> Config:
    return Config(data_dir=data_dir, static_dir=None, tz=TZ, dev=dev)


@pytest.fixture
def app(tmp_path):
    return create_app(make_config(tmp_path))


@pytest.fixture
def client(app):
    """Client that authenticates with the API token (not via Ingress)."""
    with TestClient(app, headers={"Authorization": f"Bearer {app.state.token}"}) as test_client:
        yield test_client


@pytest.fixture
def vw_up(client):
    response = client.post(
        "/api/v1/vehicles",
        json={
            "name": "VW Up",
            "make": "Volkswagen",
            "model": "Up",
            "year": 2018,
            "type": "ICE",
            "fuel_type": "petrol",
            "tank_l": 35,
            "start_odometer_km": 41000,
            "start_date": "2026-09-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
