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


def test_r2_city_state_and_wind_direction(client):
    station = {**STATION, "city": "Copenhagen", "state": "Capital Region"}
    assert client.put("/api/stations/ws-1", json=station).json()["city"] == "Copenhagen"
    body = {
        "measured_at": now(),
        "readings": [{"metric": "temperature", "value": 10}],
        "wind_direction": "NW",
    }
    assert client.post("/api/stations/ws-1/measurements", json=body).status_code == 201
    latest = client.get("/api/stations/ws-1/measurements/latest").json()
    assert latest["wind_direction"] == "NW"


def test_invalid_wind_direction_returns_422(client):
    client.put("/api/stations/ws-1", json=STATION)
    body = {
        "measured_at": now(),
        "readings": [{"metric": "temperature", "value": 10}],
        "wind_direction": "NNW-ish",
    }
    assert client.post("/api/stations/ws-1/measurements", json=body).status_code == 422


def test_r1_sqlite_database_is_migrated(tmp_path):
    """A database created before R2 (without the new columns) still works."""
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """CREATE TABLE station (station_id TEXT PRIMARY KEY, name TEXT NOT NULL,
               latitude REAL NOT NULL, longitude REAL NOT NULL, registered_at TEXT NOT NULL);
           CREATE TABLE measurement (measurement_id TEXT PRIMARY KEY, station_id TEXT NOT NULL,
               measured_at TEXT NOT NULL, received_at TEXT NOT NULL);
           INSERT INTO station VALUES ('old', 'Old', 1, 2, '2026-01-01T00:00:00+00:00');"""
    )
    conn.commit()
    conn.close()
    client = TestClient(create_app(str(path)))
    assert client.get("/api/stations/old").json()["city"] is None
