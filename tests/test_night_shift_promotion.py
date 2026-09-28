from __future__ import annotations

import pytest

from core.night_shift.contracts import (
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
)
from core.night_shift.promotion import (
    PromotionState,
    VerificationQuorum,
    decide_promotion,
)

REPO = "repo"
SHA = "d" * 40
TASK_DIGEST = "e" * 64
EVIDENCE_DIGEST = "f" * 64


def _quorum(value: bool = True) -> VerificationQuorum:
    return VerificationQuorum(
        value,
        value,
        value,
        value,
        value,
        value,
        value,
        "builder-a",
        "reviewer-b",
        SHA,
        TASK_DIGEST,
        EVIDENCE_DIGEST,
        100,
    )


def _envelope(mode: PromotionMode, risks: tuple[RiskClass, ...]) -> AutonomyEnvelope:
    return AutonomyEnvelope(
        envelope_id="night-promotion",
        issued_at_epoch=1,
        expires_at_epoch=100,
        repositories=(REPO,),
        allowed_risk_classes=risks,
        max_tasks=2,
        promotion_mode=mode,
    )


def test_incomplete_quorum_blocks() -> None:
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=_quorum(False),
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.BLOCKED


def test_r1_requires_preauthorization_for_auto() -> None:
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R1,
        envelope=_envelope(PromotionMode.PREAUTHORIZED, (RiskClass.R1,)),
        quorum=_quorum(),
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.ELIGIBLE_AUTO


def test_r2_stops_ready_for_human() -> None:
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R2,
        envelope=_envelope(PromotionMode.HUMAN, (RiskClass.R2,)),
        quorum=_quorum(),
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.READY_FOR_HUMAN


def test_promotion_rechecks_repository_authority() -> None:
    with pytest.raises(NightShiftContractError, match="repository outside authority"):
        decide_promotion(
            repository="other",
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=_quorum(),
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_promotion_rechecks_envelope_expiry() -> None:
    with pytest.raises(NightShiftContractError, match="authority envelope expired"):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=_quorum(),
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=100,
        )


def test_builder_cannot_self_certify() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="builder and reviewer identities must be different",
    ):
        VerificationQuorum(
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            "same-agent",
            "same-agent",
            SHA,
            TASK_DIGEST,
            EVIDENCE_DIGEST,
            100,
        )


def test_scope_gate_is_part_of_quorum() -> None:
    quorum = VerificationQuorum(
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        "builder-a",
        "reviewer-b",
        SHA,
        TASK_DIGEST,
        EVIDENCE_DIGEST,
        100,
    )
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.BLOCKED


def test_promotion_rejects_quorum_for_different_sha() -> None:
    with pytest.raises(NightShiftContractError, match="different SHA"):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=_quorum(),
            subject_sha="c" * 40,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_promotion_rejects_quorum_for_different_task_capsule() -> None:
    with pytest.raises(NightShiftContractError, match="different task capsule"):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=_quorum(),
            subject_sha=SHA,
            task_capsule_digest="c" * 64,
            now_epoch=10,
        )


def test_promotion_blocks_expired_verification_evidence() -> None:
    quorum = _quorum()
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=VerificationQuorum(
            quorum.focused_tests_pass,
            quorum.static_security_pass,
            quorum.scope_guard_pass,
            quorum.required_regression_pass,
            quorum.independent_review_pass,
            quorum.exact_sha_ci_pass,
            quorum.policy_engine_pass,
            quorum.builder_identity,
            quorum.reviewer_identity,
            quorum.subject_sha,
            quorum.task_capsule_digest,
            quorum.evidence_digest,
            10,
        ),
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.BLOCKED
    assert decision.reason == "verification evidence expired"
