"""Application services: the use cases of the Monitoring context.

They orchestrate the domain objects and repositories but contain no
business rules themselves (those live in the domain model).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from monitoring.domain.model import (
    CompassDirection,
    Location,
    Measurement,
    Metric,
    Reading,
    WeatherStation,
)
from monitoring.domain.repository import MeasurementRepository, StationRepository


class StationNotFoundError(Exception):
    def __init__(self, station_id: str) -> None:
        super().__init__(f"station '{station_id}' is not registered")
        self.station_id = station_id


@dataclass(frozen=True)
class ReadingInput:
    metric: str
    value: float


class MonitoringService:
    def __init__(self, stations: StationRepository, measurements: MeasurementRepository) -> None:
        self._stations = stations
        self._measurements = measurements

    # --- Use case: register (or update) a station --------------------------
    def register_station(
        self,
        station_id: str,
        name: str,
        latitude: float,
        longitude: float,
        city: str | None = None,
        state: str | None = None,
    ) -> tuple[WeatherStation, bool]:
        """Idempotent registration. Returns (station, created)."""
        location = Location(latitude, longitude, city, state)
        station = self._stations.get(station_id)
        if station is None:
            station = WeatherStation(station_id=station_id, name=name, location=location)
            self._stations.save(station)
            return station, True
        station.update_details(name, location)
        self._stations.save(station)
        return station, False

    def get_station(self, station_id: str) -> WeatherStation:
        station = self._stations.get(station_id)
        if station is None:
            raise StationNotFoundError(station_id)
        return station

    def list_stations(self) -> list[WeatherStation]:
        return self._stations.list_all()

    # --- Use case: receive a measurement from a sensor ---------------------
    def submit_measurement(
        self,
        station_id: str,
        measured_at: datetime,
        readings: list[ReadingInput],
        wind_direction: str | None = None,
    ) -> Measurement:
        station = self.get_station(station_id)
        domain_readings = [Reading(Metric(r.metric), r.value) for r in readings]
        direction = CompassDirection(wind_direction) if wind_direction else None
        measurement = station.record_measurement(measured_at, domain_readings, direction)
        self._measurements.add(measurement)
        return measurement

    # --- Use case: look at the data ----------------------------------------
    def list_measurements(self, station_id: str, limit: int = 100) -> list[Measurement]:
        self.get_station(station_id)
        return self._measurements.list_for_station(station_id, limit)

    def latest_measurement(self, station_id: str) -> Measurement | None:
        self.get_station(station_id)
        return self._measurements.latest_for_station(station_id)
