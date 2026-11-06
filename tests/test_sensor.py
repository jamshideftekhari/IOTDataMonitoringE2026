import json
import random

import pytest

from sensor.config import ConfigError, load_config
from sensor.domain import SensorSettings, SimulatedSensor
from sensor.main import build_device


def test_simulated_sensor_stays_within_bounds():
    settings = SensorSettings("temperature", start=0, min=-1, max=1, max_step=5)
    sensor = SimulatedSensor(settings, rng=random.Random(42))
    for _ in range(1000):
        assert -1 <= sensor.read().value <= 1


def test_default_config_file_loads():
    config = load_config("config/sensor_config.json")
    assert config.api.base_url == "http://127.0.0.1:8000"
    device = build_device(config)
    sample = device.take_sample()
    assert len(sample.readings) == len(config.sensors)


def test_api_address_is_read_from_config(tmp_path):
    raw = json.loads(open("config/sensor_config.json", encoding="utf-8").read())
    raw["api"]["host"] = "192.168.1.50"
    raw["api"]["port"] = 9000
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(raw))
    assert load_config(path).api.base_url == "http://192.168.1.50:9000"


def test_invalid_sensor_settings_raise_config_error(tmp_path):
    raw = json.loads(open("config/sensor_config.json", encoding="utf-8").read())
    raw["sensors"][0]["min"] = 100  # min > max
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ConfigError):
        load_config(path)


def test_wind_vane_produces_compass_points():
    from sensor.domain import COMPASS_POINTS, SimulatedWindVane, WindVaneSettings

    vane = SimulatedWindVane(WindVaneSettings(350, 30), rng=random.Random(1))
    assert all(vane.read() in COMPASS_POINTS for _ in range(500))


def test_default_config_has_r2_fields():
    config = load_config("config/sensor_config.json")
    assert config.station.city and config.station.state
    assert build_device(config).take_sample().wind_direction is not None
