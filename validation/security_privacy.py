"""Fail-closed security/privacy attestation over independent repository controls."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class SecurityControl(StrEnum):
    PII = "pii_gate"
    SECRET = "secret_gate"
    LOCAL_DATA_BOUNDARY = "local_data_boundary"
    DEPENDENCY_BOUNDARY = "dependency_boundary"
    AUDITABILITY_REVIEW = "auditability_review"


@dataclass(frozen=True, slots=True, order=True)
class SecurityControlEvidence:
    control: SecurityControl
    passed: bool
    report_sha256: str
    evidence_id: str

    def __post_init__(self) -> None:
        evidence_id = self.evidence_id.strip()
        digest = self.report_sha256.strip().lower()
        if not evidence_id:
            raise ValueError("security evidence id cannot be blank")
        if not _SHA256_RE.fullmatch(digest):
            raise ValueError("security report digest must be SHA-256")
        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "report_sha256", digest)


@dataclass(frozen=True, slots=True)
class SecurityPrivacyEvidence:
    validated_sha: str
    controls: tuple[SecurityControlEvidence, ...]
    private_case_data_committed: bool = False
    locked_evaluation_used_for_tuning: bool = False

    def __post_init__(self) -> None:
        validated_sha = self.validated_sha.strip().lower()
        if not _GIT_SHA_RE.fullmatch(validated_sha):
            raise ValueError("validated_sha must be a full hexadecimal commit SHA")
        object.__setattr__(self, "validated_sha", validated_sha)

        names = [item.control for item in self.controls]
        if len(names) != len(set(names)):
            raise ValueError("security controls must be unique")
        if self.private_case_data_committed:
            raise ValueError("private Case data cannot be committed to the public repository")
        if self.locked_evaluation_used_for_tuning:
            raise ValueError("locked evaluation cannot be used for tuning")


@dataclass(frozen=True, slots=True)
class SecurityPrivacyReport:
    validated_sha: str
    passed: bool
    controls: tuple[SecurityControlEvidence, ...]
    missing_controls: tuple[SecurityControl, ...]
    failed_controls: tuple[SecurityControl, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "controls": [
                {
                    **asdict(item),
                    "control": item.control.value,
                }
                for item in sorted(self.controls)
            ],
            "failed_controls": [item.value for item in self.failed_controls],
            "missing_controls": [item.value for item in self.missing_controls],
            "passed": self.passed,
            "validated_sha": self.validated_sha,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class SecurityPrivacyGate:
    """Require every canonical security/privacy control; missing evidence never implies PASS."""

    required_controls = frozenset(SecurityControl)

    def evaluate(self, evidence: SecurityPrivacyEvidence) -> SecurityPrivacyReport:
        by_control = {item.control: item for item in evidence.controls}
        missing = tuple(sorted(self.required_controls - set(by_control), key=str))
        failed = tuple(
            sorted(
                (control for control, item in by_control.items() if not item.passed),
                key=str,
            )
        )
        return SecurityPrivacyReport(
            validated_sha=evidence.validated_sha,
            passed=not missing and not failed,
            controls=tuple(sorted(evidence.controls)),
            missing_controls=missing,
            failed_controls=failed,
        )
