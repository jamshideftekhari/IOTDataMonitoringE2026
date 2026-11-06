"""R2 tests.

The mapping and configuration tests run offline. The integration test at the
bottom talks to the real Atlas cluster and only runs when MONGODB_PASSWORD or
MONGODB_URI is set.
"""
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from monitoring.domain.model import (
    CompassDirection,
    Location,
    Measurement,
    Metric,
    Reading,
    WeatherStation,
)
from monitoring.infrastructure.mongo_config import (
    MongoConfigError,
    MongoSettings,
    add_password,
    load_mongo_settings,
    read_compass_connection_string,
)
from monitoring.infrastructure.mongodb_repository import (
    measurement_from_document,
    measurement_to_document,
    station_from_document,
    station_to_document,
)

NY = Location(40.71, -74.0, "New York", "NY")


def sample_measurement() -> Measurement:
    return WeatherStation("A1234", "NY station", NY).record_measurement(
        datetime(2025, 8, 19, 12, 0, tzinfo=timezone.utc),
        [
            Reading(Metric.TEMPERATURE, 25.4),
            Reading(Metric.HUMIDITY, 48.2),
            Reading(Metric.PRESSURE, 1012.5),
            Reading(Metric.WIND_SPEED, 5.2),
        ],
        CompassDirection.NW,
    )


# ------------------------------------------------------------------ mapping
def test_measurement_document_has_required_shape():
    doc = measurement_to_document(sample_measurement(), NY)
    assert doc["timestamp"] == datetime(2025, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert doc["metaField"] == {
        "sensorId": "A1234",
        "location": {"city": "New York", "state": "NY"},
    }
    assert doc["temperature"] == 25.4
    assert doc["humidity"] == 48.2
    assert doc["pressure"] == 1012.5
    assert doc["windSpeed"] == 5.2
    assert doc["windDirection"] == "NW"


def test_measurement_round_trip():
    original = sample_measurement()
    restored = measurement_from_document(measurement_to_document(original, NY))
    assert restored.measurement_id == original.measurement_id
    assert restored.station_id == original.station_id
    assert restored.measured_at == original.measured_at
    assert set(restored.readings) == set(original.readings)
    assert restored.wind_direction == CompassDirection.NW


def test_missing_metrics_are_not_written():
    m = Measurement.create("A1", datetime.now(timezone.utc), [Reading(Metric.TEMPERATURE, 1)])
    doc = measurement_to_document(m, None)
    assert "humidity" not in doc and "windDirection" not in doc


def test_station_round_trip():
    station = WeatherStation("A1234", "NY station", NY)
    assert station_from_document(station_to_document(station)) == station


# ---------------------------------------------------------- wind direction
@pytest.mark.parametrize(
    "degrees,expected",
    [(0, "N"), (44, "NE"), (90, "E"), (180, "S"), (315, "NW"), (350, "N"), (-45, "NW")],
)
def test_compass_from_degrees(degrees, expected):
    assert CompassDirection.from_degrees(degrees).value == expected


# ----------------------------------------------------------- configuration
def write_compass_file(tmp_path, uri="mongodb+srv://jame@cluster0.example.mongodb.net/"):
    path = tmp_path / "compass.json"
    path.write_text(json.dumps({
        "type": "Compass Connections",
        "connections": [{
            "id": "abc",
            "favorite": {"name": "cluster0.example.mongodb.net"},
            "connectionOptions": {"connectionString": uri},
        }],
    }))
    return path


def test_read_compass_connection_string(tmp_path):
    path = write_compass_file(tmp_path)
    assert read_compass_connection_string(path) == "mongodb+srv://jame@cluster0.example.mongodb.net/"
    assert read_compass_connection_string(path, "cluster0.example.mongodb.net").startswith("mongodb")
    with pytest.raises(MongoConfigError):
        read_compass_connection_string(path, "other-cluster")


def test_password_is_url_encoded():
    uri = add_password("mongodb+srv://jame@cluster0.x.mongodb.net/", "p@ss:w/rd")
    assert uri == "mongodb+srv://jame:p%40ss%3Aw%2Frd@cluster0.x.mongodb.net/"


def test_missing_password_gives_clear_error(tmp_path):
    env = {"MONGODB_COMPASS_FILE": str(write_compass_file(tmp_path))}
    with pytest.raises(MongoConfigError, match="MONGODB_PASSWORD"):
        load_mongo_settings(env)


def test_settings_from_compass_file_and_password(tmp_path):
    env = {
        "MONGODB_COMPASS_FILE": str(write_compass_file(tmp_path)),
        "MONGODB_PASSWORD": "secret",
        "MONGODB_DATABASE": "testdb",
    }
    settings = load_mongo_settings(env)
    assert settings.uri == "mongodb+srv://jame:secret@cluster0.example.mongodb.net/"
    assert settings.database == "testdb"
    assert "secret" not in settings.redacted_uri


def test_mongodb_uri_env_overrides_file():
    settings = load_mongo_settings({"MONGODB_URI": "mongodb://localhost:27017"})
    assert settings.uri == "mongodb://localhost:27017"


# ------------------------------------------------- integration (real Atlas)
needs_atlas = pytest.mark.skipif(
    not (os.getenv("MONGODB_PASSWORD") or os.getenv("MONGODB_URI")),
    reason="set MONGODB_PASSWORD or MONGODB_URI to run against MongoDB Atlas",
)


@needs_atlas
def test_atlas_store_and_read_measurement():
    from monitoring.infrastructure.mongodb_repository import (
        MongoMeasurementRepository,
        MongoStationRepository,
        connect,
        ensure_collections,
    )

    base = load_mongo_settings()
    settings = MongoSettings(uri=base.uri, database=base.database + "_test")
    db = connect(settings)
    try:
        ensure_collections(db, settings)
        stations = MongoStationRepository(db, settings)
        measurements = MongoMeasurementRepository(db, settings, stations)

        station = WeatherStation(f"test-{uuid4().hex[:8]}", "Integration test", NY)
        stations.save(station)
        m = station.record_measurement(
            datetime.now(timezone.utc), [Reading(Metric.TEMPERATURE, 20.0)], CompassDirection.S
        )
        measurements.add(m)

        latest = measurements.latest_for_station(station.station_id)
        assert latest is not None
        assert latest.measurement_id == m.measurement_id
        assert latest.wind_direction == CompassDirection.S
    finally:
        db.client.drop_database(settings.database)
