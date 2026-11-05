from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from monitoring.api.app import create_app

STATION = {"name": "Roof", "latitude": 55.67, "longitude": 12.56}


@pytest.fixture
def client(tmp_path) -> TestClient:
    return TestClient(create_app(str(tmp_path / "test.db")))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_register_station_is_idempotent(client):
    assert client.put("/api/stations/ws-1", json=STATION).status_code == 201
    r = client.put("/api/stations/ws-1", json={**STATION, "name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert len(client.get("/api/stations").json()) == 1


def test_submit_and_read_measurement(client):
    client.put("/api/stations/ws-1", json=STATION)
    body = {
        "measured_at": now(),
        "readings": [
            {"metric": "temperature", "value": 12.3},
            {"metric": "humidity", "value": 70},
        ],
    }
    r = client.post("/api/stations/ws-1/measurements", json=body)
    assert r.status_code == 201
    latest = client.get("/api/stations/ws-1/measurements/latest").json()
    assert {x["metric"]: x["unit"] for x in latest["readings"]} == {
        "temperature": "°C",
        "humidity": "%",
    }
    assert len(client.get("/api/stations/ws-1/measurements").json()) == 1


def test_measurement_for_unknown_station_returns_404(client):
    body = {"measured_at": now(), "readings": [{"metric": "temperature", "value": 1}]}
    assert client.post("/api/stations/nope/measurements", json=body).status_code == 404


def test_out_of_range_value_returns_422(client):
    client.put("/api/stations/ws-1", json=STATION)
    body = {"measured_at": now(), "readings": [{"metric": "humidity", "value": 150}]}
    r = client.post("/api/stations/ws-1/measurements", json=body)
    assert r.status_code == 422
    assert "humidity" in r.json()["detail"]


def test_unknown_metric_returns_422(client):
    client.put("/api/stations/ws-1", json=STATION)
    body = {"measured_at": now(), "readings": [{"metric": "uv_index", "value": 3}]}
    assert client.post("/api/stations/ws-1/measurements", json=body).status_code == 422
