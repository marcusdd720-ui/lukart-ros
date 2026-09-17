"""Types and constants for LUKART Operation Contract v1."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

SCHEMA_ID = "lukart.operation-contract.v1"
SCHEMA_VERSION = "1.0"
MAX_BYTES = 262_144
MAX_ITEMS = 64
MAX_STRING = 4_096
MAX_DEPTH = 12
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[A-Za-z0-9._:/@+-]{1,256}$")
TOP_LEVEL = {
    "request",
    "context",
    "preconditions",
    "constraints",
    "idempotency",
    "effects",
    "output",
    "evidence",
    "errors",
    "privacy",
}
RAW_SECRET_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}


class OperationStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class OperationContractError(ValueError):
    """Fail-closed operation-boundary violation."""


@dataclass(frozen=True, slots=True)
class HandlerOutcome:
    status: OperationStatus | str
    summary: str
    effects: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    evidence: tuple[Mapping[str, object], ...] = ()
    errors: tuple[Mapping[str, object], ...] = ()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
