"""Domain model for the *Sensor Simulation* bounded context.

This context has its own, small model. It does not import anything from
the `monitoring` package: the two contexts only share the JSON contract
of the API (see DESIGN.md -> API documentation).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class SensorSettings:
    """Value object: how one simulated sensor behaves (from the config file)."""

    metric: str
    start: float
    min: float
    max: float
    max_step: float

    def __post_init__(self) -> None:
        if self.min > self.max:
            raise ValueError(f"{self.metric}: min ({self.min}) must be <= max ({self.max})")
        if not self.min <= self.start <= self.max:
            raise ValueError(f"{self.metric}: start must be between min and max")
        if self.max_step < 0:
            raise ValueError(f"{self.metric}: max_step must be >= 0")


@dataclass(frozen=True)
class WindVaneSettings:
    """Value object: wind direction simulation (R2)."""

    start_degrees: float = 315.0
    max_step_degrees: float = 20.0


COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def degrees_to_compass(degrees: float) -> str:
    return COMPASS_POINTS[round((degrees % 360) / 45) % 8]


@dataclass(frozen=True)
class SensorReading:
    metric: str
    value: float


@dataclass(frozen=True)
class SensorSample:
    """Everything the station measured at one point in time."""

    measured_at: datetime
    readings: tuple[SensorReading, ...]
    wind_direction: str | None = None  # "N", "NE", ... (R2)


@dataclass
class SimulatedSensor:
    """Produces realistic values with a bounded random walk."""

    settings: SensorSettings
    rng: random.Random = field(default_factory=random.Random)
    _current: float = field(init=False)

    def __post_init__(self) -> None:
        self._current = self.settings.start

    def read(self) -> SensorReading:
        s = self.settings
        step = self.rng.uniform(-s.max_step, s.max_step)
        self._current = min(s.max, max(s.min, self._current + step))
        return SensorReading(s.metric, round(self._current, 2))


@dataclass
class SimulatedWindVane:
    """Wind direction does a random walk around the compass (wraps at 360°)."""

    settings: WindVaneSettings
    rng: random.Random = field(default_factory=random.Random)
    _degrees: float = field(init=False)

    def __post_init__(self) -> None:
        self._degrees = self.settings.start_degrees % 360

    def read(self) -> str:
        step = self.rng.uniform(-self.settings.max_step_degrees, self.settings.max_step_degrees)
        self._degrees = (self._degrees + step) % 360
        return degrees_to_compass(self._degrees)


@dataclass
class WeatherStationDevice:
    """Entity: the simulated weather station with its sensors."""

    station_id: str
    name: str
    latitude: float
    longitude: float
    sensors: list[SimulatedSensor]
    wind_vane: SimulatedWindVane | None = None
    city: str | None = None
    state: str | None = None

    def take_sample(self) -> SensorSample:
        return SensorSample(
            measured_at=datetime.now(timezone.utc),
            readings=tuple(sensor.read() for sensor in self.sensors),
            wind_direction=self.wind_vane.read() if self.wind_vane else None,
        )
