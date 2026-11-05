# IoT Weather Data Monitoring

A small learning project for **Domain-Driven Design (DDD)** in Python.

A simulated weather station sends temperature, humidity, pressure and wind speed to a central
REST API, which validates the data and stores it in SQLite.
The sensor parameters and the API IP address are set in a configuration file.

See **[DESIGN.md](DESIGN.md)** for the domain model, system sequence diagrams, ER diagram and
API documentation.

## Project structure

```
IOTDataMonitoringE2026/
├── config/
│   └── sensor_config.json        # sensor parameters + API IP/port
├── monitoring/                   # Bounded context: central Monitoring API
│   ├── domain/                   #   entities, value objects, rules, repository interfaces
│   ├── application/              #   use cases (MonitoringService)
│   ├── infrastructure/           #   SQLite repositories
│   └── api/                      #   FastAPI routes + DTOs
├── sensor/                       # Bounded context: weather station simulator
│   ├── domain.py                 #   simulated sensors / station
│   ├── config.py                 #   loads the config file
│   ├── api_client.py             #   HTTP client for the API
│   └── main.py                   #   entry point
├── tests/                        # pytest tests
├── DESIGN.md
├── requirement.md
└── requirements.txt
```

## Getting started

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Start the central API

```bash
uvicorn monitoring.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- Data is saved in `monitoring.db` (change with the environment variable `MONITORING_DB`).

### 2. Start the sensor simulator (in a second terminal)

```bash
python -m sensor.main
```

Output:

```
INFO station 'ws-001' registered at http://127.0.0.1:8000
INFO sent: temperature=12.26, humidity=70.31, pressure=1012.65, wind_speed=4.48
INFO sent: temperature=12.17, humidity=69.36, pressure=1012.22, wind_speed=4.65
```

Options:

```bash
python -m sensor.main --config config/other_station.json   # another config file
python -m sensor.main --count 10                            # send 10 samples, then stop
```

### 3. Look at the data

```bash
curl http://127.0.0.1:8000/api/stations
curl http://127.0.0.1:8000/api/stations/ws-001/measurements/latest
curl "http://127.0.0.1:8000/api/stations/ws-001/measurements?limit=5"
```

## Configuration

Edit `config/sensor_config.json`:

```json
{
  "api": { "host": "127.0.0.1", "port": 8000, "timeout_seconds": 5 },
  "station": { "station_id": "ws-001", "name": "Roof station, building A",
               "latitude": 55.6761, "longitude": 12.5683 },
  "interval_seconds": 5,
  "sensors": [
    { "metric": "temperature", "start": 12.0, "min": -10.0, "max": 35.0, "max_step": 0.3 }
  ]
}
```

- To send to an API on another computer, change `api.host` to its IP address (e.g. `"192.168.1.50"`)
  and start the API with `--host 0.0.0.0`.
- Supported metrics: `temperature`, `humidity`, `pressure`, `wind_speed`.
- To simulate more stations, copy the file, change `station_id`, and start another simulator.

## Running the tests

```bash
python -m pytest
```

| File | What it tests |
|------|---------------|
| `tests/test_domain.py` | Business rules in the domain model (no database, no HTTP) |
| `tests/test_api.py` | The REST API end-to-end with a temporary database |
| `tests/test_sensor.py` | Config loading and the random-walk simulation |

## DDD concepts in this project

| Concept | Example in the code |
|---------|---------------------|
| Ubiquitous language | `WeatherStation`, `Measurement`, `Reading`, `Metric` |
| Entity | `WeatherStation` (identity = `station_id`) |
| Value object | `Location`, `Reading` (immutable, `frozen=True`) |
| Aggregate | `WeatherStation` and `Measurement`; measurement refers to the station by id |
| Factory | `WeatherStation.record_measurement()`, `Measurement.create()` |
| Repository | `StationRepository` (interface) ↔ `SqliteStationRepository` (implementation) |
| Application service | `MonitoringService` |
| Bounded context | `monitoring` and `sensor` packages, connected only through the API |
| Anti-corruption via DTOs | `monitoring/api/schemas.py` converts JSON ↔ domain objects |
