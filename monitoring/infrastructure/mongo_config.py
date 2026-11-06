"""MongoDB connection settings (R2).

The connection string is read from the MongoDB Compass export
`compass-connections.json`. Compass exports do NOT contain the password,
so it is supplied through an environment variable and never stored in a file.

Environment variables (all optional):
    MONGODB_URI            full connection string - overrides everything else
    MONGODB_PASSWORD       password inserted into the Compass connection string
    MONGODB_COMPASS_FILE   path to the Compass export   (default: compass-connections.json)
    MONGODB_CONNECTION     name or host of the connection to use (default: the first one)
    MONGODB_DATABASE       database name                (default: weather_monitoring)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlsplit, urlunsplit


class MongoConfigError(Exception):
    pass


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    database: str = "weather_monitoring"
    stations_collection: str = "stations"
    measurements_collection: str = "measurements"

    @property
    def redacted_uri(self) -> str:
        """The URI with the password hidden - safe to print or log."""
        parts = urlsplit(self.uri)
        if parts.password is None:
            return self.uri
        netloc = f"{parts.username}:****@{parts.hostname}"
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit(parts._replace(netloc=netloc))


def read_compass_connection_string(path: str | Path, name: str | None = None) -> str:
    """Return the connection string of one connection in a Compass export file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MongoConfigError(f"Compass connections file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MongoConfigError(f"{path} is not valid JSON: {exc}") from exc

    connections = data.get("connections") or []
    if not connections:
        raise MongoConfigError(f"no connections found in {path}")

    if name:
        for conn in connections:
            favorite_name = (conn.get("favorite") or {}).get("name")
            uri = conn.get("connectionOptions", {}).get("connectionString", "")
            if name in (favorite_name, conn.get("id")) or name in uri:
                break
        else:
            raise MongoConfigError(f"connection '{name}' not found in {path}")
    else:
        conn = connections[0]

    uri = conn.get("connectionOptions", {}).get("connectionString")
    if not uri:
        raise MongoConfigError(f"connection in {path} has no connectionString")
    return uri


def add_password(uri: str, password: str) -> str:
    """Insert a (URL-encoded) password into `mongodb+srv://user@host/...`."""
    parts = urlsplit(uri)
    if not parts.username:
        raise MongoConfigError("the connection string has no username to add a password to")
    if parts.password:
        return uri  # already has one
    host = parts.netloc.split("@", 1)[1]
    netloc = f"{parts.username}:{quote_plus(password)}@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def load_mongo_settings(env: dict[str, str] | None = None) -> MongoSettings:
    env = dict(os.environ) if env is None else env
    database = env.get("MONGODB_DATABASE", "weather_monitoring")

    if env.get("MONGODB_URI"):
        return MongoSettings(uri=env["MONGODB_URI"], database=database)

    uri = read_compass_connection_string(
        env.get("MONGODB_COMPASS_FILE", "compass-connections.json"),
        env.get("MONGODB_CONNECTION"),
    )
    password = env.get("MONGODB_PASSWORD")
    if password:
        uri = add_password(uri, password)
    elif urlsplit(uri).username and urlsplit(uri).password is None:
        raise MongoConfigError(
            "the connection string has a username but no password - "
            "set the environment variable MONGODB_PASSWORD"
        )
    return MongoSettings(uri=uri, database=database)
