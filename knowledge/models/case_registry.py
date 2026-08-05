"""
Registry of case workspace openers and presentation defaults.
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

    def open(self) -> "CaseWorkspace":
        return self.opener()

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
        raise KeyError(
            f"Unknown case key: {case_key!r}. Registered: {known}"
        ) from exc


def open_case(case_key: str) -> "CaseWorkspace":
    return get_spec(case_key).open()


def registered_keys() -> list[str]:
    return sorted(_REGISTRY)


def _bootstrap() -> None:
    if _REGISTRY:
        return
    from knowledge.models.case_workspace import open_ds_3960

    register(
        CaseSpec(
            key="DS_3960_2025",
            opener=open_ds_3960,
            author_name="Mariusz Brodziszewski",
            place="Poznań",
            subject=(
                "Stanowisko procesowe wraz z analizą materiału dowodowego "
                "— pojazd Volkswagen Transporter"
            ),
            recipient_lines=("Prokuratura Rejonowa Poznań-Wilda",),
            meta={"signature": "DS.3960.2025"},
        )
    )


_bootstrap()