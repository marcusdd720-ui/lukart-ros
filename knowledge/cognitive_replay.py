"""Replay binding for the typed cognitive chain without changing Case Replay v1."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from knowledge.case_replay import CaseReplayRecord

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, order=True)
class CognitiveArtifactBinding:
    artifact_type: str
    artifact_id: str
    version: int
    digest: str

    def __post_init__(self) -> None:
        if not self.artifact_type.strip() or not self.artifact_id.strip():
            raise ValueError("cognitive artifact identity cannot be empty")
        if self.version < 1:
            raise ValueError("cognitive artifact version must be >= 1")
        if not _SHA256_RE.fullmatch(self.digest):
            raise ValueError("cognitive artifact digest must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class CognitiveReplayEnvelope:
    case_replay_fingerprint: str
    artifacts: tuple[CognitiveArtifactBinding, ...]
    chain_version: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(self.case_replay_fingerprint):
            raise ValueError("case replay fingerprint must be lowercase SHA-256")
        if not self.chain_version.strip():
            raise ValueError("chain_version is required")
        identities = [(item.artifact_type, item.artifact_id) for item in self.artifacts]
        if len(identities) != len(set(identities)):
            raise ValueError("cognitive replay artifacts must be unique by type/id")

    @classmethod
    def from_case_replay(
        cls,
        case_replay: CaseReplayRecord,
        *,
        artifacts: tuple[CognitiveArtifactBinding, ...],
        chain_version: str,
    ) -> CognitiveReplayEnvelope:
        return cls(
            case_replay_fingerprint=case_replay.fingerprint(),
            artifacts=tuple(sorted(artifacts)),
            chain_version=chain_version,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_replay_fingerprint": self.case_replay_fingerprint,
            "artifacts": [
                {
                    "artifact_type": item.artifact_type,
                    "artifact_id": item.artifact_id,
                    "version": item.version,
                    "digest": item.digest,
                }
                for item in sorted(self.artifacts)
            ],
            "chain_version": self.chain_version,
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
class CognitiveReplayComparison:
    matches: bool
    expected_fingerprint: str
    observed_fingerprint: str
    drift_fields: tuple[str, ...]


def compare_cognitive_replay(
    expected: CognitiveReplayEnvelope,
    observed: CognitiveReplayEnvelope,
) -> CognitiveReplayComparison:
    expected_data = expected.canonical_dict()
    observed_data = observed.canonical_dict()
    drift = tuple(
        key for key in expected_data if expected_data[key] != observed_data.get(key)
    )
    return CognitiveReplayComparison(
        matches=not drift,
        expected_fingerprint=expected.fingerprint(),
        observed_fingerprint=observed.fingerprint(),
        drift_fields=drift,
    )
