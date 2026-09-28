"""Evidence-bound verification quorum assembly for Night Shift V2-09."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError, require_git_oid


class VerificationGate(StrEnum):
    FOCUSED_TESTS = "focused_tests"
    STATIC_SECURITY = "static_security"
    SCOPE_GUARD = "scope_guard"
    REQUIRED_REGRESSION = "required_regression"
    INDEPENDENT_REVIEW = "independent_review"
    EXACT_SHA_CI = "exact_sha_ci"
    POLICY_ENGINE = "policy_engine"


REQUIRED_VERIFICATION_GATES: tuple[VerificationGate, ...] = tuple(VerificationGate)


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    gate: VerificationGate
    passed: bool
    subject_sha: str
    task_capsule_digest: str
    producer_identity: str
    observed_at_epoch: int
    evidence_digest: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        try:
            digest = require_hex_digest(
                self.task_capsule_digest, field_name="task_capsule_digest"
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        object.__setattr__(self, "task_capsule_digest", digest)
        try:
            evidence_digest = require_hex_digest(
                self.evidence_digest, field_name="evidence_digest"
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        object.__setattr__(self, "evidence_digest", evidence_digest)
        producer = self.producer_identity.strip()
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not producer:
            raise NightShiftContractError("verification producer identity is required")
        if self.observed_at_epoch < 0:
            raise NightShiftContractError("verification observed_at_epoch cannot be negative")
        if not refs or any(not item for item in refs):
            raise NightShiftContractError("verification evidence refs are required")
        object.__setattr__(self, "producer_identity", producer)
        object.__setattr__(self, "evidence_refs", refs)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "subject_sha": self.subject_sha,
            "task_capsule_digest": self.task_capsule_digest,
            "producer_identity": self.producer_identity,
            "observed_at_epoch": self.observed_at_epoch,
            "evidence_digest": self.evidence_digest,
            "evidence_refs": list(self.evidence_refs),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class VerificationBundle:
    subject_sha: str
    task_capsule_digest: str
    builder_identity: str
    reviewer_identity: str
    evidence: tuple[VerificationEvidence, ...]

    def __post_init__(self) -> None:
        subject_sha = require_git_oid(self.subject_sha, field_name="subject_sha")
        try:
            task_digest = require_hex_digest(
                self.task_capsule_digest, field_name="task_capsule_digest"
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        builder = self.builder_identity.strip()
        reviewer = self.reviewer_identity.strip()
        if not builder or not reviewer:
            raise NightShiftContractError("builder and reviewer identities are required")
        if builder == reviewer:
            raise NightShiftContractError(
                "builder and reviewer identities must be different"
            )

        by_gate: dict[VerificationGate, VerificationEvidence] = {}
        for item in self.evidence:
            if item.gate in by_gate:
                raise NightShiftContractError(
                    f"duplicate verification evidence for {item.gate.value}"
                )
            if item.subject_sha != subject_sha:
                raise NightShiftContractError(
                    "verification evidence subject SHA does not match bundle"
                )
            if item.task_capsule_digest != task_digest:
                raise NightShiftContractError(
                    "verification evidence task capsule does not match bundle"
                )
            by_gate[item.gate] = item

        missing = [gate.value for gate in REQUIRED_VERIFICATION_GATES if gate not in by_gate]
        if missing:
            raise NightShiftContractError(
                "verification evidence incomplete: " + ",".join(missing)
            )

        review = by_gate[VerificationGate.INDEPENDENT_REVIEW]
        if review.producer_identity != reviewer:
            raise NightShiftContractError(
                "independent review evidence producer must match reviewer identity"
            )
        if review.producer_identity == builder:
            raise NightShiftContractError("builder cannot self-certify independent review")

        object.__setattr__(self, "subject_sha", subject_sha)
        object.__setattr__(self, "task_capsule_digest", task_digest)
        object.__setattr__(self, "builder_identity", builder)
        object.__setattr__(self, "reviewer_identity", reviewer)
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(self.evidence, key=lambda item: item.gate.value)),
        )

    def passed(self) -> bool:
        return all(item.passed for item in self.evidence)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "subject_sha": self.subject_sha,
            "task_capsule_digest": self.task_capsule_digest,
            "builder_identity": self.builder_identity,
            "reviewer_identity": self.reviewer_identity,
            "evidence": [item.canonical_dict() for item in self.evidence],
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def load_required_verification_gates(path: str | Path) -> tuple[VerificationGate, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("required_gates"), list):
        raise NightShiftContractError(
            "verification quorum profile must contain required_gates"
        )
    parsed: list[VerificationGate] = []
    for value in raw["required_gates"]:
        if not isinstance(value, str):
            raise NightShiftContractError("verification gate names must be strings")
        try:
            parsed.append(VerificationGate(value.strip()))
        except ValueError as exc:
            raise NightShiftContractError(
                f"unknown verification gate: {value}"
            ) from exc
    if len(set(parsed)) != len(parsed):
        raise NightShiftContractError("verification quorum profile has duplicate gates")
    if set(parsed) != set(REQUIRED_VERIFICATION_GATES):
        raise NightShiftContractError(
            "verification quorum profile does not match canonical V2-09 gates"
        )
    return tuple(parsed)


def load_verification_max_age_seconds(path: str | Path) -> int:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise NightShiftContractError("verification quorum profile must be a mapping")
    freshness = raw.get("freshness")
    if not isinstance(freshness, dict):
        raise NightShiftContractError(
            "verification quorum profile must contain freshness"
        )
    value = freshness.get("max_evidence_age_seconds")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise NightShiftContractError(
            "max_evidence_age_seconds must be a positive integer"
        )
    return value
