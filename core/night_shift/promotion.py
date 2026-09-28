"""Verification quorum and fail-closed promotion policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .contracts import (
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
)


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
    now_epoch: int,
) -> PromotionDecision:
    envelope.require_authorized(
        repository=repository,
        risk_class=risk_class,
        now_epoch=now_epoch,
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
