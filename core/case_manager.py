"""Creation and local management of MVROS case workspaces."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from core.local_case_store import case_dir, ensure_data_root


class CaseManager:
    """Create case directories only in the private local MVROS data root."""

    def __init__(self, cases_root: str | None = None):
        self.data_root = ensure_data_root(Path(cases_root).expanduser() if cases_root else None)

    @property
    def cases_root(self) -> Path:
        return self.data_root / "cases"

    def create_case(self) -> Path:
        """Create the next available private local case directory."""
        case_id = self._next_case_id()
        case_path = case_dir(case_id, self.data_root)
        case_path.mkdir(parents=True)
        for folder in (
            "original",
            "extracted",
            "markdown",
            "evidence",
            "timeline",
            "reports",
            "exports",
        ):
            (case_path / folder).mkdir()
        metadata = {
            "id": case_id,
            "title": "",
            "institution": "",
            "case_number": "",
            "status": "active",
            "created": str(date.today()),
            "version": "1.0",
        }
        with (case_path / "case.yaml").open("w", encoding="utf-8") as file:
            yaml.safe_dump(metadata, file, allow_unicode=True, sort_keys=False)
        return case_path

    def _next_case_id(self) -> str:
        existing: list[int] = []
        self.cases_root.mkdir(parents=True, exist_ok=True)
        for directory in self.cases_root.iterdir():
            if directory.is_dir() and directory.name.startswith("CASE-"):
                try:
                    existing.append(int(directory.name.split("-", 1)[1]))
                except ValueError:
                    continue
        return f"CASE-{max(existing, default=0) + 1:04d}"
