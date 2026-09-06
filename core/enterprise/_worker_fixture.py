"""Internal deterministic worker entrypoints used by Enterprise/Hardcore boundary tests."""

from __future__ import annotations

import os
import socket
import time
from collections.abc import Mapping
from pathlib import Path


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


def filesystem_read(payload: Mapping[str, object]) -> dict[str, object]:
    path = Path(str(payload.get("path", "")))
    return {"text": path.read_text(encoding="utf-8")}


def filesystem_write(payload: Mapping[str, object]) -> dict[str, object]:
    path = Path(str(payload.get("path", "")))
    text = str(payload.get("text", "worker"))
    path.write_text(text, encoding="utf-8")
    return {"written": text, "exists": path.exists()}


def process_spawn_probe(_payload: Mapping[str, object]) -> dict[str, object]:
    import subprocess
    import sys

    completed = subprocess.run(
        (sys.executable, "-c", "print('child')"),
        check=True,
        capture_output=True,
        text=True,
    )
    return {"stdout": completed.stdout.strip()}


def native_ffi_probe(_payload: Mapping[str, object]) -> dict[str, object]:
    import ctypes

    ctypes.CDLL(None)
    return {"ffi": "available"}
