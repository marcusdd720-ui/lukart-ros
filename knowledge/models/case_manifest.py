"""Canonical per-case manifest used as the runtime source of truth."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, frozen=True)
class CaseManifest:
    """Stable manifest for case identity, lifecycle and source inventory."""

    case_key: str
    case_id: str
    lifecycle_state: str = "OPEN"
    version: int = 1
    document_ids: tuple[str, ...] = field(default_factory=tuple)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_key": self.case_key,
            "case_id": self.case_id,
            "lifecycle_state": self.lifecycle_state,
            "version": self.version,
            "document_ids": sorted(set(self.document_ids)),
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def save(self, case_dir: Path) -> Path:
        case_dir = case_dir.expanduser().resolve()
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / "case_manifest.json"
        path.write_text(
            json.dumps(self.canonical_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, case_dir: Path) -> CaseManifest:
        path = case_dir.expanduser().resolve() / "case_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            case_key=str(data["case_key"]),
            case_id=str(data["case_id"]),
            lifecycle_state=str(data.get("lifecycle_state", "OPEN")),
            version=int(data.get("version", 1)),
            document_ids=tuple(str(item) for item in data.get("document_ids", [])),
        )
