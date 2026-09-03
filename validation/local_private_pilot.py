"""Local-only Step 15 pilot contracts for real private Case validation.

This module never reads private result text into a public report. A pilot result
may remain anywhere inside the validated local data root; only its SHA-256 digest
and non-sensitive execution flags enter the attestation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.local_case_store import PrivacyViolation, validate_case_key, validate_data_root

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _git_sha(value: str) -> str:
    normalized = value.strip().lower()
    if not _GIT_SHA_RE.fullmatch(normalized):
        raise ValueError("validated_sha must be a full hexadecimal commit SHA")
    return normalized


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalPilotStatus(StrEnum):
    READY_FOR_LOCAL_EXECUTION = "ready_for_local_execution"
    PASSED = "passed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LocalPrivatePilotAttestation:
    validated_sha: str
    case_fingerprint: str
    data_root_fingerprint: str
    status: LocalPilotStatus
    local_only_execution_attested: bool
    pii_not_committed: bool
    private_evidence_not_committed: bool
    pilot_results_recorded: bool
    pipeline_exit_code: int | None = None
    stages_executed: int = 0
    result_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "validated_sha", _git_sha(self.validated_sha))
        for field_name in ("case_fingerprint", "data_root_fingerprint"):
            value = str(getattr(self, field_name)).strip().lower()
            if not _SHA256_RE.fullmatch(value):
                raise ValueError(f"{field_name} must be a SHA-256 digest")
            object.__setattr__(self, field_name, value)
        if self.result_digest is not None:
            result_digest = self.result_digest.strip().lower()
            if not _SHA256_RE.fullmatch(result_digest):
                raise ValueError("result_digest must be a SHA-256 digest")
            object.__setattr__(self, "result_digest", result_digest)
        if self.stages_executed < 0:
            raise ValueError("stages_executed cannot be negative")
        if self.pilot_results_recorded:
            if self.pipeline_exit_code is None or self.result_digest is None:
                raise ValueError("recorded pilot results require exit code and result digest")
            if self.stages_executed < 1:
                raise ValueError("recorded pilot results require at least one executed stage")
        if self.status is LocalPilotStatus.PASSED and not self.passed:
            raise ValueError("PASSED status requires every Step 15 check to pass")

    @property
    def passed(self) -> bool:
        return (
            self.local_only_execution_attested
            and self.pii_not_committed
            and self.private_evidence_not_committed
            and self.pilot_results_recorded
            and self.pipeline_exit_code == 0
            and self.result_digest is not None
            and self.stages_executed > 0
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_fingerprint": self.case_fingerprint,
            "data_root_fingerprint": self.data_root_fingerprint,
            "local_only_execution_attested": self.local_only_execution_attested,
            "pii_not_committed": self.pii_not_committed,
            "pilot_results_recorded": self.pilot_results_recorded,
            "pipeline_exit_code": self.pipeline_exit_code,
            "private_evidence_not_committed": self.private_evidence_not_committed,
            "result_digest": self.result_digest,
            "stages_executed": self.stages_executed,
            "status": self.status.value,
            "validated_sha": self.validated_sha,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()


def _validated_local_context(
    *,
    case_key: str,
    data_root: Path,
    repo_root: Path,
) -> tuple[str, Path, Path]:
    key = validate_case_key(case_key)
    repo = repo_root.expanduser().resolve()
    root = validate_data_root(data_root, repo_root=repo)
    return key, root, repo


def prepare_local_private_pilot(
    *,
    case_key: str,
    data_root: Path,
    repo_root: Path,
    validated_sha: str,
) -> LocalPrivatePilotAttestation:
    """Validate local placement without claiming that the pilot has run."""

    key, root, _ = _validated_local_context(
        case_key=case_key,
        data_root=data_root,
        repo_root=repo_root,
    )
    return LocalPrivatePilotAttestation(
        validated_sha=validated_sha,
        case_fingerprint=_sha256_text(key),
        data_root_fingerprint=_sha256_text(str(root)),
        status=LocalPilotStatus.READY_FOR_LOCAL_EXECUTION,
        local_only_execution_attested=False,
        pii_not_committed=False,
        private_evidence_not_committed=False,
        pilot_results_recorded=False,
    )


def attest_local_private_pilot(
    *,
    case_key: str,
    data_root: Path,
    repo_root: Path,
    validated_sha: str,
    result_path: Path,
    pipeline_exit_code: int,
    stages_executed: int,
    pii_committed: bool,
    private_evidence_committed: bool,
) -> LocalPrivatePilotAttestation:
    """Bind Step 15 to a real local result file without exposing its path or contents."""

    key, root, repo = _validated_local_context(
        case_key=case_key,
        data_root=data_root,
        repo_root=repo_root,
    )
    result = result_path.expanduser().resolve()
    if not result.is_file():
        raise FileNotFoundError(result)
    if root != result.parent and root not in result.parents:
        raise PrivacyViolation("pilot result must remain inside the private local data root")
    if result == repo or repo in result.parents:
        raise PrivacyViolation("pilot result cannot be stored inside the Git repository")

    pii_clean = not pii_committed
    evidence_clean = not private_evidence_committed
    recorded = stages_executed > 0
    status = (
        LocalPilotStatus.PASSED
        if pipeline_exit_code == 0 and recorded and pii_clean and evidence_clean
        else LocalPilotStatus.REJECTED
    )
    return LocalPrivatePilotAttestation(
        validated_sha=validated_sha,
        case_fingerprint=_sha256_text(key),
        data_root_fingerprint=_sha256_text(str(root)),
        status=status,
        local_only_execution_attested=True,
        pii_not_committed=pii_clean,
        private_evidence_not_committed=evidence_clean,
        pilot_results_recorded=recorded,
        pipeline_exit_code=pipeline_exit_code,
        stages_executed=stages_executed,
        result_digest=_sha256_file(result),
    )


def write_local_pilot_attestation(
    attestation: LocalPrivatePilotAttestation,
    *,
    data_root: Path,
    repo_root: Path,
) -> Path:
    """Persist only the privacy-safe attestation, always outside the repository."""

    root = validate_data_root(data_root, repo_root=repo_root)
    destination = root / "pilot-attestations" / f"{attestation.case_fingerprint}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(attestation.canonical_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
