"""Canonical JSON: the one byte form used for every file controlproof writes and hashes."""

import base64
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import JsonValue


def to_json(data: Any) -> bytes:
    """Sorted keys, two-space indent, UTF-8, trailing newline."""
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def iso(value: datetime) -> str:
    """A UTC timestamp in the `...Z` form OSCAL and the run record use."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def jsonable(value: Any) -> JsonValue:
    """Convert an SDK response (datetimes, bytes, tuples) into plain JSON values."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return "base64:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(item) for item in value]
    raise TypeError(f"cannot store a {type(value).__name__} as JSON evidence")


def parse_time(value: str) -> datetime:
    """Parse an ISO 8601 timestamp from an SDK response (`...Z` or `...+00:00`)."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return parsed
