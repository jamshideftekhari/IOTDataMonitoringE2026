"""Repository interfaces (ports).

The domain only knows these abstract interfaces. The concrete storage
(SQLite, in-memory, ...) lives in the infrastructure layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .model import Measurement, WeatherStation


class StationRepository(ABC):
    @abstractmethod
    def get(self, station_id: str) -> WeatherStation | None: ...

    @abstractmethod
    def list_all(self) -> list[WeatherStation]: ...

    @abstractmethod
    def save(self, station: WeatherStation) -> None: ...


class MeasurementRepository(ABC):
    @abstractmethod
    def add(self, measurement: Measurement) -> None: ...

    @abstractmethod
    def list_for_station(self, station_id: str, limit: int = 100) -> list[Measurement]:
        """Newest first."""

    @abstractmethod
    def latest_for_station(self, station_id: str) -> Measurement | None: ...
