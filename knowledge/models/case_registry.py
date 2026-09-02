"""Registry and dynamic discovery of private local MVROS cases."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from factory.local_case_store import case_dir, ensure_data_root, validate_case_key

if TYPE_CHECKING:
    from knowledge.models.case_workspace import CaseWorkspace

OpenFn = Callable[[], "CaseWorkspace"]


@dataclass(slots=True, frozen=True)
class CaseSpec:
    """Case definition; real case data remains in the private local store."""

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
    key = validate_case_key(spec.key)
    _REGISTRY[key] = spec


def _local_case_spec(case_key: str, data_root: Path | None = None) -> CaseSpec:
    key = validate_case_key(case_key)
    root = ensure_data_root(data_root)
    path = case_dir(key, root)
    if not path.is_dir():
        raise KeyError(f"Unknown case key: {key!r}. Local case not found: {path}")

    def opener() -> CaseWorkspace:
        from knowledge.models.local_case_runtime import build_local_case_workspace

        return build_local_case_workspace(key, data_root=root)

    return CaseSpec(key=key, opener=opener)


def get_spec(case_key: str, *, data_root: Path | None = None) -> CaseSpec:
    key = validate_case_key(case_key)
    registered = _REGISTRY.get(key)
    if registered is not None:
        return registered
    return _local_case_spec(key, data_root=data_root)


def open_case(case_key: str, *, data_root: Path | None = None) -> CaseWorkspace:
    return get_spec(case_key, data_root=data_root).open(data_root=data_root)


def registered_keys(*, data_root: Path | None = None) -> list[str]:
    keys = set(_REGISTRY)
    root = ensure_data_root(data_root) / "cases"
    if root.is_dir():
        keys.update(
            path.name
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        )
    return sorted(keys)
