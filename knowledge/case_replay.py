"""Deterministic replay envelope for auditable Case executions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from knowledge.models.case_snapshot import CaseSnapshot

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, order=True)
class ReplayAgentBinding:
    agent_id: str
    agent_version: str
    contract_sha256: str

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.agent_version.strip():
            raise ValueError("agent id and version are required")
        _require_sha256("contract_sha256", self.contract_sha256)


@dataclass(frozen=True, slots=True)
class CaseReplayRecord:
    case_key: str
    snapshot_id: str
    manifest_sha256: str
    source_sha256: tuple[tuple[str, str], ...]
    pipeline_version: str
    graph_sha256: str
    agent_bindings: tuple[ReplayAgentBinding, ...]
    renderer_version: str
    git_commit: str | None = None

    def __post_init__(self) -> None:
        if not self.case_key.strip() or not self.snapshot_id.strip():
            raise ValueError("case_key and snapshot_id are required")
        if not self.pipeline_version.strip() or not self.renderer_version.strip():
            raise ValueError("pipeline_version and renderer_version are required")
        _require_sha256("manifest_sha256", self.manifest_sha256)
        _require_sha256("graph_sha256", self.graph_sha256)
        if len({name for name, _ in self.source_sha256}) != len(self.source_sha256):
            raise ValueError("source ids must be unique")
        for source_id, digest in self.source_sha256:
            if not source_id.strip():
                raise ValueError("source id is required")
            _require_sha256("source_sha256", digest)
        if len({(item.agent_id, item.agent_version) for item in self.agent_bindings}) != len(
            self.agent_bindings
        ):
            raise ValueError("agent bindings must be unique by id/version")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: CaseSnapshot,
        *,
        manifest_sha256: str,
        source_sha256: tuple[tuple[str, str], ...],
        pipeline_version: str,
        graph_sha256: str,
        agent_bindings: tuple[ReplayAgentBinding, ...],
        renderer_version: str,
    ) -> CaseReplayRecord:
        return cls(
            case_key=snapshot.case_key,
            snapshot_id=snapshot.snapshot_id,
            manifest_sha256=manifest_sha256,
            source_sha256=tuple(sorted(source_sha256)),
            pipeline_version=pipeline_version,
            graph_sha256=graph_sha256,
            agent_bindings=tuple(sorted(agent_bindings)),
            renderer_version=renderer_version,
            git_commit=snapshot.git_commit,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_key": self.case_key,
            "snapshot_id": self.snapshot_id,
            "manifest_sha256": self.manifest_sha256,
            "source_sha256": [list(item) for item in sorted(self.source_sha256)],
            "pipeline_version": self.pipeline_version,
            "graph_sha256": self.graph_sha256,
            "agent_bindings": [
                asdict(item) for item in sorted(self.agent_bindings)
            ],
            "renderer_version": self.renderer_version,
            "git_commit": self.git_commit,
        }

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CaseReplayComparison:
    matches: bool
    expected_fingerprint: str
    observed_fingerprint: str
    drift_fields: tuple[str, ...]


def compare_replay(
    expected: CaseReplayRecord,
    observed: CaseReplayRecord,
) -> CaseReplayComparison:
    expected_data = expected.canonical_dict()
    observed_data = observed.canonical_dict()
    fields = tuple(
        key
        for key in expected_data
        if expected_data[key] != observed_data.get(key)
    )
    return CaseReplayComparison(
        matches=not fields,
        expected_fingerprint=expected.fingerprint(),
        observed_fingerprint=observed.fingerprint(),
        drift_fields=fields,
    )


def _require_sha256(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
