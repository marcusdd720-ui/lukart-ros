"""
Registry of case workspace openers and presentation defaults.

Case registrations are provided explicitly by callers. The registry does not
ship with case-specific builders or dossier data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from knowledge.models.case_workspace import CaseWorkspace

OpenFn = Callable[[], "CaseWorkspace"]


@dataclass(slots=True, frozen=True)
class CaseSpec:
    """Registered case: how to open workspace + default letter/dossier fields."""

    key: str
    opener: OpenFn
    author_name: str = ""
    place: str = ""
    subject: str = ""
    recipient_lines: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, Any] = field(default_factory=dict)

    def open(self) -> CaseWorkspace:
        return self.opener()

    def run_kwargs(self) -> dict[str, Any]:
        return {
            "author_name": self.author_name,
            "place": self.place,
            "subject": self.subject,
            "recipient_lines": list(self.recipient_lines)
            if self.recipient_lines
            else None,
        }


_REGISTRY: dict[str, CaseSpec] = {}


def register(spec: CaseSpec) -> None:
    key = spec.key.strip()
    if not key:
        raise ValueError("case key cannot be empty")
    _REGISTRY[key] = spec


def get_spec(case_key: str) -> CaseSpec:
    try:
        return _REGISTRY[case_key]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown case key: {case_key!r}. Registered: {known}"
        ) from exc


def open_case(case_key: str) -> CaseWorkspace:
    return get_spec(case_key).open()


def registered_keys() -> list[str]:
    return sorted(_REGISTRY)
