"""Central Monitoring API (FastAPI).

Run:
    uvicorn monitoring.api.app:create_app --factory --host 0.0.0.0 --port 8000

Interactive docs: http://<host>:8000/docs
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from monitoring.api.schemas import (
    ErrorOut,
    MeasurementIn,
    MeasurementOut,
    StationIn,
    StationOut,
)
from monitoring.application.service import (
    MonitoringService,
    ReadingInput,
    StationNotFoundError,
)
from monitoring.domain.model import DomainError
from monitoring.infrastructure.sqlite_repository import (
    SqliteDatabase,
    SqliteMeasurementRepository,
    SqliteStationRepository,
)


def create_app(db_path: str | None = None) -> FastAPI:
    db = SqliteDatabase(db_path or os.getenv("MONITORING_DB", "monitoring.db"))
    service = MonitoringService(SqliteStationRepository(db), SqliteMeasurementRepository(db))

    app = FastAPI(
        title="IoT Weather Monitoring API",
        version="1.0.0",
        description="Central API that receives data from weather station sensors.",
    )

    # Translate domain/application errors into HTTP status codes
    @app.exception_handler(StationNotFoundError)
    async def _not_found(_: Request, exc: StationNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # ---------------------------------------------------------------- stations
    @app.put(
        "/api/stations/{station_id}",
        response_model=StationOut,
        responses={201: {"model": StationOut}, 422: {"model": ErrorOut}},
        tags=["stations"],
        summary="Register or update a weather station (idempotent)",
    )
    def register_station(station_id: str, body: StationIn, response: Response) -> StationOut:
        station, created = service.register_station(
            station_id, body.name, body.latitude, body.longitude
        )
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return StationOut.from_domain(station)

    @app.get("/api/stations", response_model=list[StationOut], tags=["stations"])
    def list_stations() -> list[StationOut]:
        return [StationOut.from_domain(s) for s in service.list_stations()]

    @app.get(
        "/api/stations/{station_id}",
        response_model=StationOut,
        responses={404: {"model": ErrorOut}},
        tags=["stations"],
    )
    def get_station(station_id: str) -> StationOut:
        return StationOut.from_domain(service.get_station(station_id))

    # ------------------------------------------------------------ measurements
    @app.post(
        "/api/stations/{station_id}/measurements",
        response_model=MeasurementOut,
        status_code=status.HTTP_201_CREATED,
        responses={404: {"model": ErrorOut}, 422: {"model": ErrorOut}},
        tags=["measurements"],
        summary="Submit a measurement from a sensor",
    )
    def submit_measurement(station_id: str, body: MeasurementIn) -> MeasurementOut:
        measurement = service.submit_measurement(
            station_id,
            body.measured_at,
            [ReadingInput(r.metric.value, r.value) for r in body.readings],
        )
        return MeasurementOut.from_domain(measurement)

    @app.get(
        "/api/stations/{station_id}/measurements",
        response_model=list[MeasurementOut],
        responses={404: {"model": ErrorOut}},
        tags=["measurements"],
        summary="List measurements, newest first",
    )
    def list_measurements(
        station_id: str, limit: int = Query(100, ge=1, le=1000)
    ) -> list[MeasurementOut]:
        return [MeasurementOut.from_domain(m) for m in service.list_measurements(station_id, limit)]

    @app.get(
        "/api/stations/{station_id}/measurements/latest",
        response_model=MeasurementOut,
        responses={404: {"model": ErrorOut}},
        tags=["measurements"],
    )
    def latest_measurement(station_id: str) -> MeasurementOut:
        m = service.latest_measurement(station_id)
        if m is None:
            raise HTTPException(status_code=404, detail="no measurements yet")
        return MeasurementOut.from_domain(m)

    return app
