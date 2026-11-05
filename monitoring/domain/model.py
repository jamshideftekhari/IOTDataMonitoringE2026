"""Domain model for the *Monitoring* bounded context (the central API side).

DDD building blocks used here:
- Value Objects : Location, Reading            (immutable, compared by value)
- Entities      : WeatherStation, Measurement  (have identity)
- Aggregate     : WeatherStation is the aggregate root for station data,
                  Measurement is its own small aggregate that references a
                  station by id (keeps aggregates small).
- Domain errors : raised when an invariant (business rule) is broken.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


# --------------------------------------------------------------------------- #
# Domain errors
# --------------------------------------------------------------------------- #
class DomainError(Exception):
    """Base class for broken business rules."""


class InvalidReadingError(DomainError):
    pass


class InvalidLocationError(DomainError):
    pass


class InvalidMeasurementError(DomainError):
    pass


# --------------------------------------------------------------------------- #
# Ubiquitous language: what can a weather station measure?
# --------------------------------------------------------------------------- #
class Metric(str, Enum):
    """The kinds of values a weather station can report.

    Each metric knows its unit and the physically plausible range.
    Values outside the range are rejected by the domain.
    """

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    WIND_SPEED = "wind_speed"

    @property
    def unit(self) -> str:
        return _METRIC_INFO[self][0]

    @property
    def valid_range(self) -> tuple[float, float]:
        return _METRIC_INFO[self][1]


_METRIC_INFO: dict[Metric, tuple[str, tuple[float, float]]] = {
    Metric.TEMPERATURE: ("°C", (-90.0, 60.0)),
    Metric.HUMIDITY: ("%", (0.0, 100.0)),
    Metric.PRESSURE: ("hPa", (850.0, 1100.0)),
    Metric.WIND_SPEED: ("m/s", (0.0, 120.0)),
}


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise InvalidLocationError(f"latitude {self.latitude} must be in [-90, 90]")
        if not -180.0 <= self.longitude <= 180.0:
            raise InvalidLocationError(f"longitude {self.longitude} must be in [-180, 180]")


@dataclass(frozen=True)
class Reading:
    """One measured value, e.g. temperature = 12.3 °C."""

    metric: Metric
    value: float

    def __post_init__(self) -> None:
        low, high = self.metric.valid_range
        if not low <= self.value <= high:
            raise InvalidReadingError(
                f"{self.metric.value}={self.value} is outside the valid range [{low}, {high}]"
            )

    @property
    def unit(self) -> str:
        return self.metric.unit


# --------------------------------------------------------------------------- #
# Entities / aggregates
# --------------------------------------------------------------------------- #
@dataclass
class WeatherStation:
    """Aggregate root: a physical (or simulated) station that sends data."""

    station_id: str
    name: str
    location: Location
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.station_id or not self.station_id.strip():
            raise DomainError("station_id must not be empty")
        if not self.name or not self.name.strip():
            raise DomainError("station name must not be empty")

    def update_details(self, name: str, location: Location) -> None:
        if not name.strip():
            raise DomainError("station name must not be empty")
        self.name = name
        self.location = location

    def record_measurement(self, measured_at: datetime, readings: list[Reading]) -> Measurement:
        """Factory method: only a known station can produce a measurement."""
        return Measurement.create(self.station_id, measured_at, readings)


@dataclass
class Measurement:
    """A set of readings taken by one station at one moment in time."""

    measurement_id: UUID
    station_id: str
    measured_at: datetime
    received_at: datetime
    readings: tuple[Reading, ...]

    @staticmethod
    def create(station_id: str, measured_at: datetime, readings: list[Reading]) -> Measurement:
        if not readings:
            raise InvalidMeasurementError("a measurement must contain at least one reading")
        metrics = [r.metric for r in readings]
        if len(metrics) != len(set(metrics)):
            raise InvalidMeasurementError("a metric may only appear once per measurement")
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)
        measured_at = measured_at.astimezone(timezone.utc)  # always store UTC
        now = datetime.now(timezone.utc)
        if (measured_at - now).total_seconds() > 60:
            raise InvalidMeasurementError("measured_at cannot be in the future")
        return Measurement(
            measurement_id=uuid4(),
            station_id=station_id,
            measured_at=measured_at,
            received_at=now,
            readings=tuple(readings),
        )

    def reading_for(self, metric: Metric) -> Reading | None:
        return next((r for r in self.readings if r.metric == metric), None)
