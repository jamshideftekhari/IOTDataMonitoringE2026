from datetime import datetime, timedelta, timezone

import pytest

from monitoring.domain.model import (
    InvalidLocationError,
    InvalidMeasurementError,
    InvalidReadingError,
    Location,
    Metric,
    Reading,
    WeatherStation,
)


def make_station() -> WeatherStation:
    return WeatherStation("ws-001", "Test", Location(55.0, 12.0))


def test_reading_knows_its_unit():
    assert Reading(Metric.TEMPERATURE, 21.5).unit == "°C"


def test_reading_outside_valid_range_is_rejected():
    with pytest.raises(InvalidReadingError):
        Reading(Metric.HUMIDITY, 120)


def test_invalid_location_is_rejected():
    with pytest.raises(InvalidLocationError):
        Location(100, 0)


def test_value_objects_compare_by_value():
    assert Reading(Metric.PRESSURE, 1000) == Reading(Metric.PRESSURE, 1000)


def test_station_records_measurement():
    m = make_station().record_measurement(
        datetime.now(timezone.utc), [Reading(Metric.TEMPERATURE, 10)]
    )
    assert m.station_id == "ws-001"
    assert m.reading_for(Metric.TEMPERATURE).value == 10


def test_measurement_requires_readings():
    with pytest.raises(InvalidMeasurementError):
        make_station().record_measurement(datetime.now(timezone.utc), [])


def test_measurement_rejects_duplicate_metric():
    with pytest.raises(InvalidMeasurementError):
        make_station().record_measurement(
            datetime.now(timezone.utc),
            [Reading(Metric.TEMPERATURE, 10), Reading(Metric.TEMPERATURE, 11)],
        )


def test_measurement_rejects_future_timestamp():
    with pytest.raises(InvalidMeasurementError):
        make_station().record_measurement(
            datetime.now(timezone.utc) + timedelta(hours=1), [Reading(Metric.TEMPERATURE, 10)]
        )
