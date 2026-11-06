"""SQLite implementation of the repositories (adapter).

Table layout matches the ER diagram in DESIGN.md:
    station (1) ──< measurement (1) ──< reading
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from uuid import UUID

from monitoring.domain.model import CompassDirection, Location, Measurement, Metric, Reading, WeatherStation
from monitoring.domain.repository import MeasurementRepository, StationRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS station (
    station_id     TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    latitude       REAL NOT NULL,
    longitude      REAL NOT NULL,
    city           TEXT,
    state          TEXT,
    registered_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurement (
    measurement_id TEXT PRIMARY KEY,
    station_id     TEXT NOT NULL REFERENCES station(station_id),
    measured_at    TEXT NOT NULL,
    received_at    TEXT NOT NULL,
    wind_direction TEXT
);
CREATE INDEX IF NOT EXISTS ix_measurement_station_time
    ON measurement (station_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS reading (
    measurement_id TEXT NOT NULL REFERENCES measurement(measurement_id) ON DELETE CASCADE,
    metric         TEXT NOT NULL,
    value          REAL NOT NULL,
    unit           TEXT NOT NULL,
    PRIMARY KEY (measurement_id, metric)
);
"""


class SqliteDatabase:
    """Owns one shared connection (fine for a small single-process API)."""

    def __init__(self, path: str = "monitoring.db") -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.lock = threading.Lock()

    def _migrate(self) -> None:
        """Add columns introduced in R2 to a database created with R1."""
        new_columns = {
            "station": {"city": "TEXT", "state": "TEXT"},
            "measurement": {"wind_direction": "TEXT"},
        }
        for table, columns in new_columns.items():
            existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for column, sql_type in columns.items():
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
        self.conn.commit()


class SqliteStationRepository(StationRepository):
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def get(self, station_id: str) -> WeatherStation | None:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT * FROM station WHERE station_id = ?", (station_id,)
            ).fetchone()
        return _row_to_station(row) if row else None

    def list_all(self) -> list[WeatherStation]:
        with self._db.lock:
            rows = self._db.conn.execute("SELECT * FROM station ORDER BY station_id").fetchall()
        return [_row_to_station(r) for r in rows]

    def save(self, station: WeatherStation) -> None:
        with self._db.lock, self._db.conn:
            self._db.conn.execute(
                """INSERT INTO station
                       (station_id, name, latitude, longitude, city, state, registered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(station_id) DO UPDATE SET
                       name = excluded.name,
                       latitude = excluded.latitude,
                       longitude = excluded.longitude,
                       city = excluded.city,
                       state = excluded.state""",
                (
                    station.station_id,
                    station.name,
                    station.location.latitude,
                    station.location.longitude,
                    station.location.city,
                    station.location.state,
                    station.registered_at.isoformat(),
                ),
            )


class SqliteMeasurementRepository(MeasurementRepository):
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def add(self, measurement: Measurement) -> None:
        with self._db.lock, self._db.conn:
            self._db.conn.execute(
                """INSERT INTO measurement
                       (measurement_id, station_id, measured_at, received_at, wind_direction)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    str(measurement.measurement_id),
                    measurement.station_id,
                    measurement.measured_at.isoformat(),
                    measurement.received_at.isoformat(),
                    measurement.wind_direction.value if measurement.wind_direction else None,
                ),
            )
            self._db.conn.executemany(
                "INSERT INTO reading (measurement_id, metric, value, unit) VALUES (?, ?, ?, ?)",
                [
                    (str(measurement.measurement_id), r.metric.value, r.value, r.unit)
                    for r in measurement.readings
                ],
            )

    def list_for_station(self, station_id: str, limit: int = 100) -> list[Measurement]:
        with self._db.lock:
            rows = self._db.conn.execute(
                """SELECT * FROM measurement WHERE station_id = ?
                   ORDER BY measured_at DESC LIMIT ?""",
                (station_id, limit),
            ).fetchall()
            return [self._load(r) for r in rows]

    def latest_for_station(self, station_id: str) -> Measurement | None:
        result = self.list_for_station(station_id, limit=1)
        return result[0] if result else None

    def _load(self, row: sqlite3.Row) -> Measurement:
        readings = self._db.conn.execute(
            "SELECT metric, value FROM reading WHERE measurement_id = ?",
            (row["measurement_id"],),
        ).fetchall()
        return Measurement(
            measurement_id=UUID(row["measurement_id"]),
            station_id=row["station_id"],
            measured_at=datetime.fromisoformat(row["measured_at"]),
            received_at=datetime.fromisoformat(row["received_at"]),
            readings=tuple(Reading(Metric(r["metric"]), r["value"]) for r in readings),
            wind_direction=(
                CompassDirection(row["wind_direction"]) if row["wind_direction"] else None
            ),
        )


def _row_to_station(row: sqlite3.Row) -> WeatherStation:
    return WeatherStation(
        station_id=row["station_id"],
        name=row["name"],
        location=Location(row["latitude"], row["longitude"], row["city"], row["state"]),
        registered_at=datetime.fromisoformat(row["registered_at"]),
    )
