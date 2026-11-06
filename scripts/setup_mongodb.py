"""R2 - Check the MongoDB Atlas connection and create the time-series collection.

Run from the project root:
    python -m scripts.setup_mongodb

Safe to run more than once (it only creates what is missing).
Connection settings: see monitoring/infrastructure/mongo_config.py
(at least MONGODB_PASSWORD must be set when using compass-connections.json).
"""
from __future__ import annotations

import sys

from pymongo.errors import PyMongoError

from monitoring.infrastructure.mongo_config import MongoConfigError, load_mongo_settings
from monitoring.infrastructure.mongodb_repository import connect, ensure_collections


def main() -> int:
    try:
        settings = load_mongo_settings()
    except MongoConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1

    print(f"Connecting to {settings.redacted_uri}")
    try:
        db = connect(settings)
        db.client.admin.command("ping")
        print("  ping ............................ OK")
        print(f"  server version .................. {db.client.server_info()['version']}")

        ensure_collections(db, settings)
        info = db.command("listCollections", filter={"name": settings.measurements_collection})
        options = info["cursor"]["firstBatch"][0]["options"]
        print(f"  database ........................ {settings.database}")
        print(f"  time-series collection .......... {settings.measurements_collection}")
        print(f"      options ..................... {options.get('timeseries')}")
        print(f"  stations collection ............. {settings.stations_collection}")
        print(f"  measurements stored ............. "
              f"{db[settings.measurements_collection].count_documents({})}")
    except PyMongoError as exc:
        print(f"MongoDB error: {exc}")
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
