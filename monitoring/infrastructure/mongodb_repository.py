"""MongoDB Atlas implementation of the repositories (R2).

Measurements are stored in a MongoDB *time-series collection*:

    {
      "_id": "294a3f8b-...",                       # measurement_id
      "timestamp": ISODate("2025-08-19T12:00:00Z"), # timeField
      "metaField": {                               # metaField (what the series is about)
        "sensorId": "A1234",
        "location": {"city": "New York", "state": "NY"}
      },
      "temperature": 25.4,
      "humidity": 48.2,
      "pressure": 1012.5,
      "windSpeed": 5.2,
      "windDirection": "NW",
      "receivedAt": ISODate(...)
    }

Stations are stored in a normal collection.

Only this file knows the document layout. The domain model and the
application service are exactly the same for SQLite and MongoDB - that is
the point of the Repository pattern.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from monitoring.domain.model import (
    CompassDirection,
    Location,
    Measurement,
    Metric,
    Reading,
    WeatherStation,
)
from monitoring.domain.repository import MeasurementRepository, StationRepository
from monitoring.infrastructure.mongo_config import MongoSettings

# Domain metric  ->  field name in the MongoDB document (camelCase as required)
METRIC_FIELDS: dict[Metric, str] = {
    Metric.TEMPERATURE: "temperature",
    Metric.HUMIDITY: "humidity",
    Metric.PRESSURE: "pressure",
    Metric.WIND_SPEED: "windSpeed",
}
FIELD_METRICS = {field: metric for metric, field in METRIC_FIELDS.items()}


# --------------------------------------------------------------------------- #
# Connection and collection setup
# --------------------------------------------------------------------------- #
def connect(settings: MongoSettings, timeout_ms: int = 10_000) -> Database:
    client: MongoClient = MongoClient(
        settings.uri, tz_aware=True, serverSelectionTimeoutMS=timeout_ms
    )
    return client[settings.database]


def ensure_collections(db: Database, settings: MongoSettings) -> None:
    """Create the time-series collection and indexes if they do not exist (idempotent)."""
    try:
        db.create_collection(
            settings.measurements_collection,
            timeseries={
                "timeField": "timestamp",
                "metaField": "metaField",
                "granularity": "seconds",
            },
        )
    except CollectionInvalid:
        pass  # already exists

    db[settings.measurements_collection].create_index(
        [("metaField.sensorId", ASCENDING), ("timestamp", DESCENDING)],
        name="sensor_time",
    )


# --------------------------------------------------------------------------- #
# Mapping domain <-> document (pure functions, easy to unit test)
# --------------------------------------------------------------------------- #
def station_to_document(station: WeatherStation) -> dict[str, Any]:
    loc = station.location
    return {
        "_id": station.station_id,
        "name": station.name,
        "location": {
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "city": loc.city,
            "state": loc.state,
        },
        "registeredAt": station.registered_at,
    }


def station_from_document(doc: dict[str, Any]) -> WeatherStation:
    loc = doc["location"]
    return WeatherStation(
        station_id=doc["_id"],
        name=doc["name"],
        location=Location(loc["latitude"], loc["longitude"], loc.get("city"), loc.get("state")),
        registered_at=_utc(doc["registeredAt"]),
    )


def measurement_to_document(m: Measurement, location: Location | None) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "_id": str(m.measurement_id),
        "timestamp": m.measured_at,
        "metaField": {
            "sensorId": m.station_id,
            "location": {
                "city": location.city if location else None,
                "state": location.state if location else None,
            },
        },
    }
    for reading in m.readings:
        doc[METRIC_FIELDS[reading.metric]] = reading.value
    if m.wind_direction is not None:
        doc["windDirection"] = m.wind_direction.value
    doc["receivedAt"] = m.received_at
    return doc


def measurement_from_document(doc: dict[str, Any]) -> Measurement:
    readings = tuple(
        Reading(metric, doc[field]) for field, metric in FIELD_METRICS.items() if field in doc
    )
    timestamp = _utc(doc["timestamp"])
    return Measurement(
        measurement_id=UUID(str(doc["_id"])),
        station_id=doc["metaField"]["sensorId"],
        measured_at=timestamp,
        received_at=_utc(doc.get("receivedAt", timestamp)),
        readings=readings,
        wind_direction=(
            CompassDirection(doc["windDirection"]) if doc.get("windDirection") else None
        ),
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #
class MongoStationRepository(StationRepository):
    def __init__(self, db: Database, settings: MongoSettings) -> None:
        self._col = db[settings.stations_collection]

    def get(self, station_id: str) -> WeatherStation | None:
        doc = self._col.find_one({"_id": station_id})
        return station_from_document(doc) if doc else None

    def list_all(self) -> list[WeatherStation]:
        return [station_from_document(d) for d in self._col.find().sort("_id", ASCENDING)]

    def save(self, station: WeatherStation) -> None:
        doc = station_to_document(station)
        self._col.replace_one({"_id": doc["_id"]}, doc, upsert=True)


class MongoMeasurementRepository(MeasurementRepository):
    def __init__(self, db: Database, settings: MongoSettings, stations: StationRepository) -> None:
        self._col = db[settings.measurements_collection]
        # Needed to fill metaField.location - the document stores the station's
        # city/state together with every measurement (denormalised on purpose,
        # so time-series queries can filter by city without a join).
        self._stations = stations

    def add(self, measurement: Measurement) -> None:
        station = self._stations.get(measurement.station_id)
        location = station.location if station else None
        self._col.insert_one(measurement_to_document(measurement, location))

    def list_for_station(self, station_id: str, limit: int = 100) -> list[Measurement]:
        cursor = (
            self._col.find({"metaField.sensorId": station_id})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        return [measurement_from_document(d) for d in cursor]

    def latest_for_station(self, station_id: str) -> Measurement | None:
        result = self.list_for_station(station_id, limit=1)
        return result[0] if result else None
