"""Internal deterministic worker entrypoints used by Enterprise boundary tests."""

from __future__ import annotations

import os
import socket
import time
from collections.abc import Mapping


def echo(payload: Mapping[str, object]) -> dict[str, object]:
    return {"echo": dict(payload), "isolation": os.environ.get("LUKART_WORKER_ISOLATION", "")}


def delayed(payload: Mapping[str, object]) -> dict[str, object]:
    raw_seconds = payload.get("seconds", 0.0)
    if not isinstance(raw_seconds, str | int | float):
        raise ValueError("seconds must be numeric")
    seconds = float(raw_seconds)
    time.sleep(seconds)
    return {"slept": seconds}


def environment_snapshot(payload: Mapping[str, object]) -> dict[str, object]:
    key = str(payload.get("key", ""))
    return {"key": key, "value": os.environ.get(key)}


def network_probe(_payload: Mapping[str, object]) -> dict[str, object]:
    try:
        socket.getaddrinfo("example.com", 443)
    except Exception as exc:
        return {"network": "denied", "error_type": type(exc).__name__}
    return {"network": "available"}
