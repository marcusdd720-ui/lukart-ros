from __future__ import annotations

import pytest

from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import (
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
)
from core.night_shift.crypto_identity import (
    VerificationCryptoContext,
    sign_verification_bundle,
)
from core.night_shift.promotion import (
    PromotionState,
    VerificationQuorum,
    decide_promotion,
    quorum_from_bundle,
)
from core.night_shift.shadow import ShadowPromotionClearance
from core.night_shift.verification import (
    VerificationBundle,
    VerificationEvidence,
    VerificationGate,
)

REPO = "repo"
SHA = "d" * 40
TASK_DIGEST = "e" * 64
EVIDENCE_DIGEST = "f" * 64
LEDGER_DIGEST = "a" * 64


def _clearance(
    *,
    debt_value: int = 0,
    sample_count: int = 3,
    minimum_samples_for_auto: int = 3,
    repository: str = REPO,
    subject_sha: str = SHA,
    task_capsule_digest: str = TASK_DIGEST,
    expires_at_epoch: int = 100,
) -> ShadowPromotionClearance:
    return ShadowPromotionClearance(
        repository=repository,
        subject_sha=subject_sha,
        task_capsule_digest=task_capsule_digest,
        ledger_digest=LEDGER_DIGEST,
        debt_value=debt_value,
        downgrade_threshold=10,
        sample_count=sample_count,
        minimum_samples_for_auto=minimum_samples_for_auto,
        issued_at_epoch=1,
        expires_at_epoch=expires_at_epoch,
    )


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




def _signed_quorum() -> tuple[VerificationQuorum, VerificationCryptoContext]:
    builder = AttestationSigner.generate("builder-a")
    reviewer = AttestationSigner.generate("reviewer-b")
    trust_set = CryptoTrustSetV1(
        keys=(
            CryptoTrustKeyV1.from_public_key_bytes(
                key_id=builder.key_id,
                public_key=builder.public_key_bytes(),
                status=CryptoKeyStatus.ACTIVE,
                not_before=1,
                allowed_purposes=(AttestationPurpose.PROVENANCE,),
            ),
            CryptoTrustKeyV1.from_public_key_bytes(
                key_id=reviewer.key_id,
                public_key=reviewer.public_key_bytes(),
                status=CryptoKeyStatus.ACTIVE,
                not_before=1,
                allowed_purposes=(AttestationPurpose.SECURITY_REVIEW,),
            ),
        )
    )
    evidence = tuple(
        VerificationEvidence(
            gate=gate,
            passed=True,
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            producer_identity=(
                reviewer.key_id
                if gate is VerificationGate.INDEPENDENT_REVIEW
                else builder.key_id
            ),
            observed_at_epoch=10,
            evidence_digest=("a" if gate is VerificationGate.FOCUSED_TESTS else "b") * 64,
            evidence_refs=(f"test:{gate.value}",),
        )
        for gate in VerificationGate
    )
    bundle = VerificationBundle(
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        builder_identity=builder.key_id,
        reviewer_identity=reviewer.key_id,
        evidence=evidence,
    )
    quorum = quorum_from_bundle(
        bundle,
        now_epoch=10,
        max_evidence_age_seconds=90,
    )
    signed = sign_verification_bundle(
        bundle=bundle,
        quorum_digest=quorum.digest(),
        evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_signer=builder,
        reviewer_signer=reviewer,
        issued_at=10,
        nonce_prefix="promotion-test",
    )
    return quorum, VerificationCryptoContext(
        bundle=bundle,
        signed=signed,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
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
    quorum, crypto = _signed_quorum()
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R1,
        envelope=_envelope(PromotionMode.PREAUTHORIZED, (RiskClass.R1,)),
        quorum=quorum,
        crypto_context=crypto,
        shadow_clearance=_clearance(),
        expected_shadow_ledger_digest=LEDGER_DIGEST,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.ELIGIBLE_AUTO
    assert decision.cryptographic_verification_digest is not None
    assert decision.shadow_clearance_digest == _clearance().digest()


def test_r2_stops_ready_for_human() -> None:
    quorum, crypto = _signed_quorum()
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R2,
        envelope=_envelope(PromotionMode.HUMAN, (RiskClass.R2,)),
        quorum=quorum,
        crypto_context=crypto,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.READY_FOR_HUMAN
    assert decision.cryptographic_verification_digest is not None


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


def test_passing_quorum_without_crypto_context_fails_closed() -> None:
    quorum, _ = _signed_quorum()
    with pytest.raises(
        NightShiftContractError,
        match="cryptographic verification context is required",
    ):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=quorum,
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_r0_without_shadow_clearance_downgrades_to_human() -> None:
    quorum, crypto = _signed_quorum()
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        crypto_context=crypto,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.READY_FOR_HUMAN
    assert decision.reason == "shadow promotion clearance required"
    assert decision.shadow_clearance_digest is None


def test_r0_with_shadow_clearance_is_eligible_auto() -> None:
    quorum, crypto = _signed_quorum()
    clearance = _clearance()
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        crypto_context=crypto,
        shadow_clearance=clearance,
        expected_shadow_ledger_digest=LEDGER_DIGEST,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.ELIGIBLE_AUTO
    assert decision.shadow_clearance_digest == clearance.digest()


def test_shadow_clearance_with_insufficient_samples_downgrades_to_human() -> None:
    quorum, crypto = _signed_quorum()
    clearance = _clearance(sample_count=2)
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        crypto_context=crypto,
        shadow_clearance=clearance,
        expected_shadow_ledger_digest=LEDGER_DIGEST,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.READY_FOR_HUMAN
    assert decision.reason == "insufficient shadow calibration samples"
    assert decision.shadow_clearance_digest == clearance.digest()


def test_shadow_debt_threshold_downgrades_to_human() -> None:
    quorum, crypto = _signed_quorum()
    clearance = _clearance(debt_value=10)
    decision = decide_promotion(
        repository=REPO,
        risk_class=RiskClass.R0,
        envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
        quorum=quorum,
        crypto_context=crypto,
        shadow_clearance=clearance,
        expected_shadow_ledger_digest=LEDGER_DIGEST,
        subject_sha=SHA,
        task_capsule_digest=TASK_DIGEST,
        now_epoch=10,
    )
    assert decision.state is PromotionState.READY_FOR_HUMAN
    assert decision.reason == "autonomy debt threshold reached"
    assert decision.shadow_clearance_digest == clearance.digest()


@pytest.mark.parametrize(
    ("clearance", "match"),
    (
        (_clearance(repository="other"), "different repository"),
        (_clearance(subject_sha="c" * 40), "different SHA"),
        (
            _clearance(task_capsule_digest="c" * 64),
            "different task capsule",
        ),
    ),
)
def test_shadow_clearance_identity_mismatch_fails_closed(
    clearance: ShadowPromotionClearance,
    match: str,
) -> None:
    quorum, crypto = _signed_quorum()
    with pytest.raises(NightShiftContractError, match=match):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=quorum,
            crypto_context=crypto,
            shadow_clearance=clearance,
            expected_shadow_ledger_digest=LEDGER_DIGEST,
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_expired_shadow_clearance_fails_closed() -> None:
    quorum, crypto = _signed_quorum()
    with pytest.raises(NightShiftContractError, match="clearance expired"):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=quorum,
            crypto_context=crypto,
            shadow_clearance=_clearance(expires_at_epoch=10),
            expected_shadow_ledger_digest=LEDGER_DIGEST,
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_auto_promotion_requires_shadow_ledger_authority() -> None:
    quorum, crypto = _signed_quorum()
    with pytest.raises(
        NightShiftContractError,
        match="shadow ledger digest authority is required",
    ):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=quorum,
            crypto_context=crypto,
            shadow_clearance=_clearance(),
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )


def test_forged_shadow_clearance_ledger_digest_fails_closed() -> None:
    quorum, crypto = _signed_quorum()
    with pytest.raises(
        NightShiftContractError,
        match="does not match expected autonomy debt ledger",
    ):
        decide_promotion(
            repository=REPO,
            risk_class=RiskClass.R0,
            envelope=_envelope(PromotionMode.AUTO, (RiskClass.R0,)),
            quorum=quorum,
            crypto_context=crypto,
            shadow_clearance=_clearance(),
            expected_shadow_ledger_digest="b" * 64,
            subject_sha=SHA,
            task_capsule_digest=TASK_DIGEST,
            now_epoch=10,
        )
