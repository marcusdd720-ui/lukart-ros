"""Strict configuration scalar validation for Night Shift profiles."""

from __future__ import annotations

from .contracts import NightShiftContractError


def require_bool(value: object, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise NightShiftContractError(f"{field_name} must be a boolean")
    return value


def require_nonnegative_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise NightShiftContractError(f"{field_name} must be a non-negative integer")
    return value


def require_positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value < 1:
        raise NightShiftContractError(f"{field_name} must be a positive integer")
    return value


def require_string_list(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise NightShiftContractError(f"{field_name} must be a list of strings")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise NightShiftContractError(f"{field_name} must contain nonblank strings")
        normalized.append(item.strip())
    if not normalized:
        raise NightShiftContractError(f"{field_name} cannot be empty")
    return tuple(normalized)


def require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NightShiftContractError(f"{field_name} must be a nonblank string")
    return value.strip()
