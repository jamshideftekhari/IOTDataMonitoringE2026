"""Weather station sensor simulator.

Run:
    python -m sensor.main                          # uses config/sensor_config.json
    python -m sensor.main --config my_config.json
    python -m sensor.main --count 10               # send 10 samples and stop
"""
from __future__ import annotations

import argparse
import logging
import time

from sensor.api_client import ApiError, MonitoringApiClient
from sensor.config import AppConfig, ConfigError, load_config
from sensor.domain import SimulatedSensor, WeatherStationDevice

log = logging.getLogger("sensor")


def build_device(config: AppConfig) -> WeatherStationDevice:
    st = config.station
    return WeatherStationDevice(
        station_id=st.station_id,
        name=st.name,
        latitude=st.latitude,
        longitude=st.longitude,
        sensors=[SimulatedSensor(s) for s in config.sensors],
    )


def run(config: AppConfig, client: MonitoringApiClient, count: int | None = None) -> None:
    device = build_device(config)

    # 1. Register the station (retry until the API is reachable)
    while True:
        try:
            client.register_station(config.station)
            log.info("station '%s' registered at %s", device.station_id, config.api.base_url)
            break
        except ApiError as exc:
            log.warning("%s - retrying in %ss", exc, config.interval_seconds)
            time.sleep(config.interval_seconds)

    # 2. Loop: take a sample and send it
    sent = 0
    while count is None or sent < count:
        sample = device.take_sample()
        try:
            client.send_sample(device.station_id, sample)
            values = ", ".join(f"{r.metric}={r.value}" for r in sample.readings)
            log.info("sent: %s", values)
        except ApiError as exc:
            log.error("could not send sample: %s", exc)
        sent += 1
        if count is None or sent < count:
            time.sleep(config.interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather station sensor simulator")
    parser.add_argument("--config", default="config/sensor_config.json")
    parser.add_argument("--count", type=int, default=None, help="number of samples (default: forever)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))

    try:
        run(config, MonitoringApiClient(config.api), args.count)
    except KeyboardInterrupt:
        log.info("stopped")


if __name__ == "__main__":
    main()
