"""Registry of private local case workspace openers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from factory.local_case_store import ensure_data_root

if TYPE_CHECKING:
    from knowledge.models.case_workspace import CaseWorkspace

OpenFn = Callable[[], "CaseWorkspace"]


@dataclass(slots=True, frozen=True)
class CaseSpec:
    """Registered case definition; data remains in the local private store."""

    key: str
    opener: OpenFn
    author_name: str = ""
    place: str = ""
    subject: str = ""
    recipient_lines: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, Any] = field(default_factory=dict)

    def open(self, *, data_root: Path | None = None) -> CaseWorkspace:
        ws = self.opener()
        ws.root = ensure_data_root(data_root)
        return ws

    def run_kwargs(self) -> dict[str, Any]:
        return {
            "author_name": self.author_name,
            "place": self.place,
            "subject": self.subject,
            "recipient_lines": list(self.recipient_lines) if self.recipient_lines else None,
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
        raise KeyError(f"Unknown case key: {case_key!r}. Registered: {known}") from exc


def open_case(case_key: str, *, data_root: Path | None = None) -> CaseWorkspace:
    return get_spec(case_key).open(data_root=data_root)


def registered_keys() -> list[str]:
    return sorted(_REGISTRY)
