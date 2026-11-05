"""Data Transfer Objects (DTOs) for the HTTP API.

DTOs are *not* the domain model: they describe the JSON on the wire and
are translated to/from domain objects in app.py.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from monitoring.domain.model import Measurement, Metric, WeatherStation


class StationIn(BaseModel):
    name: str = Field(..., min_length=1, examples=["Roof station, building A"])
    latitude: float = Field(..., examples=[55.6761])
    longitude: float = Field(..., examples=[12.5683])


class StationOut(BaseModel):
    station_id: str
    name: str
    latitude: float
    longitude: float
    registered_at: datetime

    @staticmethod
    def from_domain(s: WeatherStation) -> StationOut:
        return StationOut(
            station_id=s.station_id,
            name=s.name,
            latitude=s.location.latitude,
            longitude=s.location.longitude,
            registered_at=s.registered_at,
        )


class ReadingIn(BaseModel):
    metric: Metric
    value: float


class ReadingOut(BaseModel):
    metric: Metric
    value: float
    unit: str


class MeasurementIn(BaseModel):
    measured_at: datetime
    readings: list[ReadingIn] = Field(..., min_length=1)


class MeasurementOut(BaseModel):
    measurement_id: UUID
    station_id: str
    measured_at: datetime
    received_at: datetime
    readings: list[ReadingOut]

    @staticmethod
    def from_domain(m: Measurement) -> MeasurementOut:
        return MeasurementOut(
            measurement_id=m.measurement_id,
            station_id=m.station_id,
            measured_at=m.measured_at,
            received_at=m.received_at,
            readings=[ReadingOut(metric=r.metric, value=r.value, unit=r.unit) for r in m.readings],
        )


class ErrorOut(BaseModel):
    detail: str
