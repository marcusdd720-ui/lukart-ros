"""Validation primitives for LUKART Operation Contract v1."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .types_v1 import (
    ID_RE,
    MAX_DEPTH,
    MAX_ITEMS,
    MAX_STRING,
    RAW_SECRET_KEYS,
    SHA40_RE,
    OperationContractError,
)


def require_map(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise OperationContractError(f"{field} must be an object")
    return value


def require_string(value: object, field: str, limit: int = MAX_STRING) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperationContractError(f"{field} must be a non-blank string")
    if value != value.strip():
        raise OperationContractError(f"{field} must not contain surrounding whitespace")
    if len(value) > limit:
        raise OperationContractError(f"{field} exceeds maximum length {limit}")
    return value


def require_id(value: object, field: str) -> str:
    value = require_string(value, field, 256)
    if not ID_RE.fullmatch(value):
        raise OperationContractError(f"{field} contains unsupported characters")
    return value


def require_sha(value: object, field: str) -> str:
    value = require_string(value, field, 40)
    if not SHA40_RE.fullmatch(value):
        raise OperationContractError(f"{field} must be a lowercase 40-character SHA")
    return value


def require_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise OperationContractError(f"{field} must be an array")
    if len(value) > MAX_ITEMS:
        raise OperationContractError(f"{field} exceeds maximum item count")
    items = tuple(require_id(item, f"{field}[]") for item in value)
    if len(items) != len(set(items)):
        raise OperationContractError(f"{field} cannot contain duplicates")
    return items


def exact_keys(mapping: Mapping[str, object], keys: set[str], field: str) -> None:
    if set(mapping) == keys:
        return
    missing = ",".join(sorted(keys - set(mapping))) or "-"
    extra = ",".join(sorted(set(mapping) - keys)) or "-"
    raise OperationContractError(f"{field} keys invalid (missing={missing} extra={extra})")


def _secret_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in RAW_SECRET_KEYS:
        return True
    suffixes = ("_token", "_password", "_secret", "_api_key", "_private_key")
    return normalized.endswith(suffixes) or normalized.endswith("_credential")


def check_bounded(value: object, field: str = "envelope", depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise OperationContractError(f"{field} exceeds maximum nesting depth")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OperationContractError(f"{field} contains a non-finite number")
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING:
            raise OperationContractError(f"{field} contains an oversized string")
        return
    if isinstance(value, Mapping):
        if len(value) > 128:
            raise OperationContractError(f"{field} object is oversized")
        for key, item in value.items():
            if not isinstance(key, str):
                raise OperationContractError(f"{field} keys must be strings")
            if _secret_key(key):
                raise OperationContractError(f"{field} contains forbidden raw-secret field: {key}")
            check_bounded(item, f"{field}.{key}", depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > MAX_ITEMS:
            raise OperationContractError(f"{field} array is oversized")
        for index, item in enumerate(value):
            check_bounded(item, f"{field}[{index}]", depth + 1)
        return
    raise OperationContractError(f"{field} contains non-JSON-compatible data")
