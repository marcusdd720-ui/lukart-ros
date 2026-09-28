"""Deterministic fixture entrypoints for Night Shift executor-adapter validation."""

from __future__ import annotations

from collections.abc import Mapping


def canonical_echo(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "executor": "deterministic_local",
        "payload": dict(payload),
        "status": "PASS",
    }


def attempt_network(_payload: Mapping[str, object]) -> dict[str, object]:
    import socket

    socket.create_connection(("127.0.0.1", 9), timeout=0.1)
    return {"status": "UNEXPECTED"}
