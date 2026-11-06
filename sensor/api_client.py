"""HTTP adapter that talks to the central Monitoring API."""
from __future__ import annotations

import requests

from sensor.config import ApiSettings, StationSettings
from sensor.domain import SensorSample


class ApiError(Exception):
    pass


class MonitoringApiClient:
    def __init__(self, settings: ApiSettings, session: requests.Session | None = None) -> None:
        self._settings = settings
        self._session = session or requests.Session()

    def register_station(self, station: StationSettings) -> None:
        self._request(
            "PUT",
            f"/api/stations/{station.station_id}",
            {
                "name": station.name,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "city": station.city,
                "state": station.state,
            },
        )

    def send_sample(self, station_id: str, sample: SensorSample) -> dict:
        return self._request(
            "POST",
            f"/api/stations/{station_id}/measurements",
            {
                "measured_at": sample.measured_at.isoformat(),
                "readings": [{"metric": r.metric, "value": r.value} for r in sample.readings],
                "wind_direction": sample.wind_direction,
            },
        )

    def _request(self, method: str, path: str, body: dict) -> dict:
        url = self._settings.base_url + path
        try:
            resp = self._session.request(
                method, url, json=body, timeout=self._settings.timeout_seconds
            )
        except requests.RequestException as exc:
            raise ApiError(f"cannot reach API at {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise ApiError(f"{method} {path} failed: {resp.status_code} {resp.text}")
        return resp.json()
