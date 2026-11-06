"""R2 - Show the latest time-series documents stored in MongoDB Atlas.

Run from the project root:
    python -m scripts.show_measurements                    # 10 newest, all sensors
    python -m scripts.show_measurements --sensor ws-001 --limit 5
    python -m scripts.show_measurements --stats            # avg/min/max per sensor (last 24h)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from bson import json_util
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from monitoring.infrastructure.mongo_config import MongoConfigError, load_mongo_settings
from monitoring.infrastructure.mongodb_repository import connect


def show_latest(collection, sensor: str | None, limit: int) -> None:
    query = {"metaField.sensorId": sensor} if sensor else {}
    for doc in collection.find(query).sort("timestamp", DESCENDING).limit(limit):
        print(json_util.dumps(doc, indent=2, json_options=json_util.RELAXED_JSON_OPTIONS))


def show_stats(collection, sensor: str | None) -> None:
    """Example of a time-series aggregation: statistics per sensor for the last 24 hours."""
    match: dict = {"timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}}
    if sensor:
        match["metaField.sensorId"] = sensor
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$metaField.sensorId",
                "count": {"$sum": 1},
                "avgTemperature": {"$avg": "$temperature"},
                "minTemperature": {"$min": "$temperature"},
                "maxTemperature": {"$max": "$temperature"},
                "avgHumidity": {"$avg": "$humidity"},
                "avgPressure": {"$avg": "$pressure"},
                "maxWindSpeed": {"$max": "$windSpeed"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = list(collection.aggregate(pipeline))
    if not rows:
        print("No measurements in the last 24 hours.")
    for row in rows:
        print(f"Sensor {row['_id']}  ({row['count']} measurements, last 24h)")
        for key, value in row.items():
            if key not in ("_id", "count") and value is not None:
                print(f"  {key:<16} {value:8.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show weather measurements stored in MongoDB")
    parser.add_argument("--sensor", help="sensorId / station_id, e.g. ws-001")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--stats", action="store_true", help="show statistics instead")
    args = parser.parse_args()

    try:
        settings = load_mongo_settings()
        collection = connect(settings)[settings.measurements_collection]
        if args.stats:
            show_stats(collection, args.sensor)
        else:
            show_latest(collection, args.sensor, args.limit)
    except (MongoConfigError, PyMongoError) as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
