"""
Registry of local case workspace openers and presentation defaults.

Case registrations are intentionally not stored in the public repository.
A case must be registered by the local application layer at runtime.
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
    """Registered local case: workspace opener and presentation defaults."""

    key: str
    opener: OpenFn
    author_name: str = ""
    place: str = ""
    subject: str = ""
    recipient_lines: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, Any] = field(default_factory=dict)

    def open(self) -> "CaseWorkspace":
        return self.opener()

    def run_kwargs(self) -> dict[str, Any]:
        return {
            "author_name": self.author_name,
            "place": self.place,
            "subject": self.subject,
            "recipient_lines": (
                list(self.recipient_lines) if self.recipient_lines else None
            ),
        }


_REGISTRY: dict[str, CaseSpec] = {}


def register(spec: CaseSpec) -> None:
    """Register a local case specification at runtime."""
    key = spec.key.strip()
    if not key:
        raise ValueError("case key cannot be empty")
    _REGISTRY[key] = spec


def get_spec(case_key: str) -> CaseSpec:
    """Return a registered local case specification."""
    try:
        return _REGISTRY[case_key]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown case key: {case_key!r}. Registered: {known}"
        ) from exc


def open_case(case_key: str) -> "CaseWorkspace":
    """Open a case registered by the local application layer."""
    return get_spec(case_key).open()


def registered_keys() -> list[str]:
    """Return locally registered case keys."""
    return sorted(_REGISTRY)
