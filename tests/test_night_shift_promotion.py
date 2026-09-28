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
        now_epoch=10,
    )
    assert decision.state is PromotionState.BLOCKED


def test_r1_requires_preauthorization_for_auto() -> None:
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R1,
        envelope=_envelope(PromotionMode.PREAUTHORIZED, (RiskClass.R1,)),
        quorum=_quorum(),
        now_epoch=10,
    )
    assert decision.state is PromotionState.ELIGIBLE_AUTO


def test_r2_stops_ready_for_human() -> None:
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R2,
        envelope=_envelope(PromotionMode.HUMAN, (RiskClass.R2,)),
        quorum=_quorum(),
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
            now_epoch=10,
        )


def test_promotion_rechecks_envelope_expiry() -> None:
    with pytest.raises(NightShiftContractError, match="authority envelope expired"):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=_quorum(),
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
    )
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        now_epoch=10,
    )
    assert decision.state is PromotionState.BLOCKED
