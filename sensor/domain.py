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
class SensorReading:
    metric: str
    value: float


@dataclass(frozen=True)
class SensorSample:
    """Everything the station measured at one point in time."""

    measured_at: datetime
    readings: tuple[SensorReading, ...]


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
class WeatherStationDevice:
    """Entity: the simulated weather station with its sensors."""

    station_id: str
    name: str
    latitude: float
    longitude: float
    sensors: list[SimulatedSensor]

    def take_sample(self) -> SensorSample:
        return SensorSample(
            measured_at=datetime.now(timezone.utc),
            readings=tuple(sensor.read() for sensor in self.sensors),
        )
