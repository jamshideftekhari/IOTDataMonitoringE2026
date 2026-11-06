"""Loads the sensor configuration file (sensor parameters + API address)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sensor.domain import SensorSettings, WindVaneSettings


@dataclass(frozen=True)
class ApiSettings:
    host: str
    port: int
    timeout_seconds: float = 5.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True)
class StationSettings:
    station_id: str
    name: str
    latitude: float
    longitude: float
    city: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class AppConfig:
    api: ApiSettings
    station: StationSettings
    interval_seconds: float
    sensors: tuple[SensorSettings, ...]
    wind_vane: WindVaneSettings | None = None


class ConfigError(Exception):
    pass


def load_config(path: str | Path) -> AppConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file is not valid JSON: {exc}") from exc

    try:
        config = AppConfig(
            api=ApiSettings(**raw["api"]),
            station=StationSettings(**raw["station"]),
            interval_seconds=float(raw.get("interval_seconds", 5)),
            sensors=tuple(SensorSettings(**s) for s in raw["sensors"]),
            wind_vane=WindVaneSettings(**raw["wind_direction"]) if "wind_direction" in raw else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc

    if config.interval_seconds <= 0:
        raise ConfigError("interval_seconds must be > 0")
    if not config.sensors:
        raise ConfigError("at least one sensor must be configured")
    return config
