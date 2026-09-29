from dataclasses import replace

import pytest

from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_promotion_readiness import (
    RuntimePromotionReadinessPolicy,
    RuntimePromotionReadinessStatus,
    evaluate_runtime_promotion_readiness,
    sign_runtime_promotion_review,
)
from core.night_shift.runtime_shadow_activation_evidence import (
    RuntimeShadowEvidenceCandidate,
    RuntimeShadowEvidenceResult,
    RuntimeShadowEvidenceStatus,
)
from core.p3.contracts import content_digest

BUILDER = "night-shift-builder"
NOW = 10
VALID_UNTIL = 100


def _shadow_evidence() -> RuntimeShadowEvidenceResult:
    candidates = tuple(
        RuntimeShadowEvidenceCandidate(
            runtime_id=runtime_id,
            plan_candidate_digest=content_digest({"plan": runtime_id}),
            run_digests=(
                content_digest({"run": runtime_id, "index": 0}),
                content_digest({"run": runtime_id, "index": 1}),
                content_digest({"run": runtime_id, "index": 2}),
            ),
            ready_for_promotion_review=True,
            blockers=(),
        )
        for runtime_id in ("dbos", "temporal")
    )
    return RuntimeShadowEvidenceResult(
        status=RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW,
        policy_digest=content_digest({"policy": "v2-22"}),
        plan_digest=content_digest({"plan": "v2-21"}),
        candidates=candidates,
        blockers=(),
    )


def _trust_fixture() -> tuple[
    AttestationSigner,
    AttestationSigner,
    CryptoTrustSetV1,
]:
    first = AttestationSigner.generate("promotion-reviewer-a")
    second = AttestationSigner.generate("promotion-reviewer-b")
    trust_set = CryptoTrustSetV1(
        keys=tuple(
            CryptoTrustKeyV1.from_public_key_bytes(
                key_id=signer.key_id,
                public_key=signer.public_key_bytes(),
                status=CryptoKeyStatus.ACTIVE,
                not_before=1,
                allowed_purposes=(AttestationPurpose.SECURITY_REVIEW,),
            )
            for signer in (first, second)
        )
    )
    return first, second, trust_set


def _reviews(
    shadow: RuntimeShadowEvidenceResult,
    *,
    approved: bool = True,
):
    first, second, trust_set = _trust_fixture()
    reviews = tuple(
        sign_runtime_promotion_review(
            shadow_evidence=shadow,
            runtime_id=candidate.runtime_id,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            builder_identity=BUILDER,
            reviewer_signer=signer,
            approved=approved,
            issued_at=NOW,
            expires_at=VALID_UNTIL,
            nonce=f"{candidate.runtime_id}:{signer.key_id}",
        )
        for candidate in shadow.candidates
        for signer in (first, second)
    )
    return reviews, trust_set


def test_v223_prepares_only_human_promotion_decision() -> None:
    shadow = _shadow_evidence()
    reviews, trust_set = _reviews(shadow)
    result = evaluate_runtime_promotion_readiness(
        shadow_evidence=shadow,
        reviews=reviews,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER,
        now_epoch=NOW + 1,
        policy=RuntimePromotionReadinessPolicy(),
    )

    assert (
        result.status
        is RuntimePromotionReadinessStatus.READY_FOR_HUMAN_PROMOTION_DECISION
    )
    assert all(
        item.ready_for_human_promotion_decision for item in result.candidates
    )
    assert all(len(item.verified_review_digests) == 2 for item in result.candidates)
    assert not result.promotion_executed
    assert not result.production_publication_executed


def test_v223_requires_two_distinct_verified_reviewers_per_runtime() -> None:
    shadow = _shadow_evidence()
    reviews, trust_set = _reviews(shadow)
    reduced = tuple(
        item
        for item in reviews
        if item.reviewer_identity == "promotion-reviewer-a"
    )
    result = evaluate_runtime_promotion_readiness(
        shadow_evidence=shadow,
        reviews=reduced,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER,
        now_epoch=NOW + 1,
        policy=RuntimePromotionReadinessPolicy(),
    )

    assert result.status is RuntimePromotionReadinessStatus.BLOCKED
    assert "INSUFFICIENT_DISTINCT_REVIEWERS" in result.candidates[0].blockers


def test_v223_builder_cannot_self_approve() -> None:
    shadow = _shadow_evidence()
    signer = AttestationSigner.generate(BUILDER)
    trust_set = CryptoTrustSetV1(
        keys=(
            CryptoTrustKeyV1.from_public_key_bytes(
                key_id=signer.key_id,
                public_key=signer.public_key_bytes(),
                status=CryptoKeyStatus.ACTIVE,
                not_before=1,
                allowed_purposes=(AttestationPurpose.SECURITY_REVIEW,),
            ),
        )
    )

    with pytest.raises(
        NightShiftContractError,
        match="builder cannot self-approve",
    ):
        sign_runtime_promotion_review(
            shadow_evidence=shadow,
            runtime_id="dbos",
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            builder_identity=BUILDER,
            reviewer_signer=signer,
            approved=True,
            issued_at=NOW,
            expires_at=VALID_UNTIL,
            nonce="self-review",
        )


def test_v223_tampered_approval_invalidates_signature() -> None:
    shadow = _shadow_evidence()
    reviews, trust_set = _reviews(shadow)
    poisoned = replace(reviews[0], approved=False)

    with pytest.raises(NightShiftContractError):
        evaluate_runtime_promotion_readiness(
            shadow_evidence=shadow,
            reviews=(poisoned,) + reviews[1:],
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            builder_identity=BUILDER,
            now_epoch=NOW + 1,
            policy=RuntimePromotionReadinessPolicy(),
        )

def test_v223_ready_result_cannot_carry_blockers() -> None:
    shadow = _shadow_evidence()
    reviews, trust_set = _reviews(shadow)
    result = evaluate_runtime_promotion_readiness(
        shadow_evidence=shadow,
        reviews=reviews,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER,
        now_epoch=NOW + 1,
        policy=RuntimePromotionReadinessPolicy(),
    )

    with pytest.raises(
        NightShiftContractError,
        match="ready runtime promotion result cannot carry blockers",
    ):
        replace(result, blockers=("FORGED_BLOCKER",))
