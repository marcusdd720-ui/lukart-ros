"""
Registry of case workspace openers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.models.case_workspace import CaseWorkspace

OpenFn = Callable[[], "CaseWorkspace"]

_REGISTRY: dict[str, OpenFn] = {}


def register(case_key: str, opener: OpenFn) -> None:
    key = case_key.strip()
    if not key:
        raise ValueError("case_key cannot be empty")
    _REGISTRY[key] = opener


def open_case(case_key: str) -> "CaseWorkspace":
    try:
        opener = _REGISTRY[case_key]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown case key: {case_key!r}. Registered: {known}"
        ) from exc
    return opener()


def registered_keys() -> list[str]:
    return sorted(_REGISTRY)


def _bootstrap() -> None:
    if _REGISTRY:
        return
    from knowledge.models.case_workspace import open_ds_3960

    register("DS_3960_2025", open_ds_3960)


_bootstrap()