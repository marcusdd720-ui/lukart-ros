"""Verification quorum and fail-closed promotion policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import (
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
    require_git_oid,
)
from .verification import VerificationBundle


class PromotionState(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN = "READY_FOR_HUMAN"
    ELIGIBLE_AUTO = "ELIGIBLE_AUTO"


@dataclass(frozen=True, slots=True)
class VerificationQuorum:
    focused_tests_pass: bool
    static_security_pass: bool
    scope_guard_pass: bool
    required_regression_pass: bool
    independent_review_pass: bool
    exact_sha_ci_pass: bool
    policy_engine_pass: bool
    builder_identity: str
    reviewer_identity: str
    subject_sha: str
    task_capsule_digest: str
    evidence_digest: str
    evidence_valid_until_epoch: int

    def __post_init__(self) -> None:
        builder = self.builder_identity.strip()
        reviewer = self.reviewer_identity.strip()
        if not builder or not reviewer:
            raise NightShiftContractError(
                "builder and reviewer identities are required"
            )
        if builder == reviewer:
            raise NightShiftContractError(
                "builder and reviewer identities must be different"
            )
        object.__setattr__(self, "builder_identity", builder)
        object.__setattr__(self, "reviewer_identity", reviewer)
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        for field_name in ("task_capsule_digest", "evidence_digest"):
            try:
                normalized = require_hex_digest(
                    getattr(self, field_name), field_name=field_name
                )
            except ValueError as exc:
                raise NightShiftContractError(str(exc)) from exc
            object.__setattr__(self, field_name, normalized)
        if self.evidence_valid_until_epoch < 0:
            raise NightShiftContractError(
                "evidence_valid_until_epoch cannot be negative"
            )

    def passed(self) -> bool:
        return all(
            (
                self.focused_tests_pass,
                self.static_security_pass,
                self.scope_guard_pass,
                self.required_regression_pass,
                self.independent_review_pass,
                self.exact_sha_ci_pass,
                self.policy_engine_pass,
            )
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "focused_tests_pass": self.focused_tests_pass,
            "static_security_pass": self.static_security_pass,
            "scope_guard_pass": self.scope_guard_pass,
            "required_regression_pass": self.required_regression_pass,
            "independent_review_pass": self.independent_review_pass,
            "exact_sha_ci_pass": self.exact_sha_ci_pass,
            "policy_engine_pass": self.policy_engine_pass,
            "builder_identity": self.builder_identity,
            "reviewer_identity": self.reviewer_identity,
            "subject_sha": self.subject_sha,
            "task_capsule_digest": self.task_capsule_digest,
            "evidence_digest": self.evidence_digest,
            "evidence_valid_until_epoch": self.evidence_valid_until_epoch,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: PromotionState
    reason: str


def decide_promotion(
    *,
    repository: str,
    risk_class: RiskClass,
    envelope: AutonomyEnvelope,
    quorum: VerificationQuorum,
    subject_sha: str,
    task_capsule_digest: str,
    now_epoch: int,
) -> PromotionDecision:
    expected_sha = require_git_oid(subject_sha, field_name="subject_sha")
    try:
        expected_task_digest = require_hex_digest(
            task_capsule_digest, field_name="task_capsule_digest"
        )
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc
    if quorum.subject_sha != expected_sha:
        raise NightShiftContractError("verification quorum is bound to a different SHA")
    if quorum.task_capsule_digest != expected_task_digest:
        raise NightShiftContractError(
            "verification quorum is bound to a different task capsule"
        )
    envelope.require_authorized(
        repository=repository,
        risk_class=risk_class,
        now_epoch=now_epoch,
    )
    if now_epoch >= quorum.evidence_valid_until_epoch:
        return PromotionDecision(
            PromotionState.BLOCKED,
            "verification evidence expired",
        )
    if not quorum.passed():
        return PromotionDecision(PromotionState.BLOCKED, "verification quorum incomplete")

    if risk_class in {RiskClass.R2, RiskClass.R3, RiskClass.R4}:
        return PromotionDecision(
            PromotionState.READY_FOR_HUMAN,
            f"{risk_class.value} requires human promotion authority",
        )

    if envelope.promotion_mode is PromotionMode.HUMAN:
        return PromotionDecision(
            PromotionState.READY_FOR_HUMAN,
            "authority envelope requires human promotion",
        )

    if risk_class is RiskClass.R1:
        if envelope.promotion_mode is PromotionMode.PREAUTHORIZED:
            return PromotionDecision(
                PromotionState.ELIGIBLE_AUTO,
                "R1 pre-authorized and verification quorum passed",
            )
        return PromotionDecision(
            PromotionState.READY_FOR_HUMAN,
            "R1 lacks pre-authorized promotion authority",
        )

    if risk_class is RiskClass.R0:
        return PromotionDecision(
            PromotionState.ELIGIBLE_AUTO,
            "R0 verification quorum passed under unattended authority",
        )

    return PromotionDecision(PromotionState.BLOCKED, "unsupported promotion state")


def quorum_from_bundle(
    bundle: VerificationBundle,
    *,
    now_epoch: int,
    max_evidence_age_seconds: int,
) -> VerificationQuorum:
    if now_epoch < 0:
        raise NightShiftContractError("now_epoch cannot be negative")
    if max_evidence_age_seconds <= 0:
        raise NightShiftContractError(
            "max_evidence_age_seconds must be positive"
        )
    observed = tuple(item.observed_at_epoch for item in bundle.evidence)
    if any(item > now_epoch for item in observed):
        raise NightShiftContractError(
            "verification evidence cannot be observed in the future"
        )
    valid_until = min(observed) + max_evidence_age_seconds
    if now_epoch >= valid_until:
        raise NightShiftContractError("verification evidence expired")

    by_gate = {item.gate.value: item for item in bundle.evidence}
    return VerificationQuorum(
        focused_tests_pass=by_gate["focused_tests"].passed,
        static_security_pass=by_gate["static_security"].passed,
        scope_guard_pass=by_gate["scope_guard"].passed,
        required_regression_pass=by_gate["required_regression"].passed,
        independent_review_pass=by_gate["independent_review"].passed,
        exact_sha_ci_pass=by_gate["exact_sha_ci"].passed,
        policy_engine_pass=by_gate["policy_engine"].passed,
        builder_identity=bundle.builder_identity,
        reviewer_identity=bundle.reviewer_identity,
        subject_sha=bundle.subject_sha,
        task_capsule_digest=bundle.task_capsule_digest,
        evidence_digest=bundle.digest(),
        evidence_valid_until_epoch=valid_until,
    )
