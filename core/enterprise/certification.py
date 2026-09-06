"""E10 Enterprise engineering/certification gate.

Automation can establish engineering evidence completeness, but cannot self-assert a human or
external security review. Enterprise Candidate status requires a separately signed review artifact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import (
    AttestationPurpose,
    AttestationVerifier,
    EnterpriseContractError,
    SignedAttestation,
)

_REQUIRED_STAGES = tuple(f"E{index}" for index in range(10))


class EnterpriseGateState(StrEnum):
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    INDEPENDENT_REVIEW_REQUIRED = "INDEPENDENT_REVIEW_REQUIRED"
    ENTERPRISE_CANDIDATE = "ENTERPRISE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class ControlEvidence:
    stage: str
    passed: bool
    evidence_digest: str
    detail: str

    def __post_init__(self) -> None:
        stage = self.stage.strip().upper()
        if stage not in _REQUIRED_STAGES:
            raise EnterpriseContractError(f"unknown Enterprise stage evidence: {stage}")
        require_hex_digest(self.evidence_digest, field_name="evidence_digest")
        if not self.detail.strip():
            raise EnterpriseContractError("control evidence detail is required")
        object.__setattr__(self, "stage", stage)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "evidence_digest": self.evidence_digest,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class EnterpriseGateResult:
    state: EnterpriseGateState
    candidate_sha: str
    evidence_bundle_digest: str
    missing_stages: tuple[str, ...]
    failed_stages: tuple[str, ...]
    independent_review_digest: str | None = None


class EnterpriseCertificationGate:
    def evaluate(
        self,
        *,
        candidate_sha: str,
        evidence: Sequence[ControlEvidence],
    ) -> EnterpriseGateResult:
        sha = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40, 64))
        by_stage: dict[str, ControlEvidence] = {}
        for item in evidence:
            if item.stage in by_stage:
                raise EnterpriseContractError(f"duplicate Enterprise evidence: {item.stage}")
            by_stage[item.stage] = item
        missing = tuple(stage for stage in _REQUIRED_STAGES if stage not in by_stage)
        failed = tuple(
            stage for stage in _REQUIRED_STAGES if stage in by_stage and not by_stage[stage].passed
        )
        bundle = {
            "candidate_sha": sha,
            "evidence": [by_stage[stage].canonical_dict() for stage in sorted(by_stage)],
        }
        digest = content_digest(bundle)
        if failed:
            state = EnterpriseGateState.FAIL
        elif missing:
            state = EnterpriseGateState.INCOMPLETE
        else:
            state = EnterpriseGateState.INDEPENDENT_REVIEW_REQUIRED
        return EnterpriseGateResult(
            state=state,
            candidate_sha=sha,
            evidence_bundle_digest=digest,
            missing_stages=missing,
            failed_stages=failed,
        )

    def apply_independent_review(
        self,
        result: EnterpriseGateResult,
        *,
        review_payload: Mapping[str, object],
        review_attestation: SignedAttestation,
        verifier: AttestationVerifier,
        now: int,
    ) -> EnterpriseGateResult:
        if result.state is not EnterpriseGateState.INDEPENDENT_REVIEW_REQUIRED:
            raise EnterpriseContractError("engineering gate is not ready for independent review")
        review_digest = verifier.verify(
            review_attestation,
            expected_purpose=AttestationPurpose.SECURITY_REVIEW,
            expected_subject_digest=result.evidence_bundle_digest,
            payload=review_payload,
            now=now,
        )
        reviewer = str(review_payload.get("reviewer_id", "")).strip()
        scope = str(review_payload.get("scope", "")).strip()
        if not reviewer or not scope:
            raise EnterpriseContractError("independent review payload lacks reviewer identity/scope")
        return EnterpriseGateResult(
            state=EnterpriseGateState.ENTERPRISE_CANDIDATE,
            candidate_sha=result.candidate_sha,
            evidence_bundle_digest=result.evidence_bundle_digest,
            missing_stages=(),
            failed_stages=(),
            independent_review_digest=review_digest,
        )
