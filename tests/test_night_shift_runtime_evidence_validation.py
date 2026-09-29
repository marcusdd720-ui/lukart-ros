from __future__ import annotations

import base64
from dataclasses import replace
from pathlib import Path

import pytest

from core.crypto_agility_v1 import (
    CryptoKeyStatus,
    CryptoTrustKeyV1,
    CryptoTrustSetV1,
)
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_evidence_acquisition import (
    RuntimeEvidenceAcquisitionPolicy,
    RuntimeEvidenceRun,
    evaluate_runtime_evidence_acquisition,
)
from core.night_shift.runtime_evidence_validation import (
    RuntimeEvidenceValidationPolicy,
    RuntimeEvidenceValidationStatus,
    evaluate_runtime_evidence_validation,
    sign_runtime_evidence_review,
)
from core.night_shift.runtime_profiles import (
    RuntimeEvidence,
    RuntimeProfile,
    load_runtime_profiles,
)
from core.night_shift.runtime_scale_benchmark import RuntimeBenchmarkSample
from core.p3.contracts import content_digest

_MATRIX = Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
REPO_SHA = "a" * 40
BUILDER_IDENTITY = "night-shift-builder"
NOW = 10
VALID_UNTIL = 100
BUILDER = "runtime-builder"


def _candidate_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    profiles = load_runtime_profiles(_MATRIX)
    dbos = next(item for item in profiles if item.runtime_id == "dbos")
    temporal = next(item for item in profiles if item.runtime_id == "temporal")
    return dbos, temporal


def _concrete_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    dbos, temporal = _candidate_profiles()
    return (
        replace(dbos, adapter="DBOSWorkflowEngine"),
        replace(temporal, adapter="TemporalWorkflowEngine"),
    )


def _sample(profile: RuntimeProfile, index: int) -> RuntimeBenchmarkSample:
    return RuntimeBenchmarkSample(
        runtime_profile_digest=profile.digest(),
        sample_id=f"{profile.runtime_id}-sample-{index:02d}",
        crash_resume_pass=True,
        idempotency_pass=True,
        deterministic_replay_pass=True,
        durable_timer_pass=True,
        distributed_workers_pass=True,
        setup_ms=100 + index,
        recovery_ms=50 + index,
        evidence_refs=(f"artifact:{profile.runtime_id}:sample:{index}",),
    )


def _run(
    profile: RuntimeProfile,
    sample: RuntimeBenchmarkSample,
    index: int,
) -> RuntimeEvidenceRun:
    return RuntimeEvidenceRun(
        runtime_id=profile.runtime_id,
        runtime_profile_digest=profile.digest(),
        benchmark_sample_digest=sample.digest(),
        run_id=f"{profile.runtime_id}-run-{index:02d}",
        executor_id=f"executor-{index:02d}",
        adapter=profile.adapter,
        adapter_version="1.2.3",
        environment_digest=content_digest(
            {"environment": profile.runtime_id, "run": index}
        ),
        artifact_digest=content_digest(
            {"artifact": profile.runtime_id, "run": index}
        ),
        evidence_refs=(f"artifact:{profile.runtime_id}:run:{index}",),
    )


def _acquisition(profiles: tuple[RuntimeProfile, RuntimeProfile]):
    samples = tuple(
        _sample(profile, index)
        for profile in profiles
        for index in range(3)
    )
    sample_by_key = {
        (sample.runtime_profile_digest, sample.sample_id): sample
        for sample in samples
    }
    runs = tuple(
        _run(
            profile,
            sample_by_key[
                (
                    profile.digest(),
                    f"{profile.runtime_id}-sample-{index:02d}",
                )
            ],
            index,
        )
        for profile in profiles
        for index in range(3)
    )
    return evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=runs,
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )


def _trust_fixture() -> tuple[
    AttestationSigner,
    AttestationSigner,
    CryptoTrustSetV1,
]:
    first = AttestationSigner.generate("runtime-reviewer-1")
    second = AttestationSigner.generate("runtime-reviewer-2")
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


def _signed_reviews(
    profiles: tuple[RuntimeProfile, RuntimeProfile],
):
    acquisition = _acquisition(profiles)
    first, second, trust_set = _trust_fixture()
    reviews = tuple(
        sign_runtime_evidence_review(
            acquisition=acquisition,
            profile=profile,
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            reviewer_signer=signer,
            issued_at=NOW,
            expires_at=VALID_UNTIL,
            nonce=f"{profile.runtime_id}:{signer.key_id}",
        )
        for profile in profiles
        for signer in (first, second)
    )
    return acquisition, reviews, trust_set, first, second


def test_two_distinct_crypto_reviews_prepare_signed_matrix_change() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)

    result = evaluate_runtime_evidence_validation(
        acquisition=acquisition,
        profiles=profiles,
        reviews=reviews,
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        now_epoch=NOW,
        policy=RuntimeEvidenceValidationPolicy(),
    )

    assert (
        result.status
        is RuntimeEvidenceValidationStatus.READY_FOR_SIGNED_MATRIX_CHANGE
    )
    assert result.blockers == ()
    assert all(item.ready_for_signed_matrix_change for item in result.candidates)
    assert all(
        item.target_evidence is RuntimeEvidence.VALIDATED
        for item in result.candidates
    )
    assert all(
        len(item.verified_review_digests) == 2
        for item in result.candidates
    )
    assert all(
        profile.evidence is RuntimeEvidence.DOCUMENTED for profile in profiles
    )
    assert result.automatic_matrix_mutation_executed is False


def test_current_placeholder_matrix_remains_blocked() -> None:
    profiles = _candidate_profiles()
    acquisition = _acquisition(profiles)
    _, _, trust_set = _trust_fixture()

    result = evaluate_runtime_evidence_validation(
        acquisition=acquisition,
        profiles=profiles,
        reviews=(),
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        now_epoch=NOW,
        policy=RuntimeEvidenceValidationPolicy(),
    )

    assert result.status is RuntimeEvidenceValidationStatus.BLOCKED
    assert result.blockers == ("RUNTIME_VALIDATION_INCOMPLETE",)
    assert all(
        "ACQUISITION_NOT_READY" in item.blockers
        for item in result.candidates
    )


def test_review_threshold_and_auto_mutation_cannot_be_weakened() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="at least two review identities",
    ):
        RuntimeEvidenceValidationPolicy(
            min_independent_reviews_per_runtime=1
        )

    with pytest.raises(
        NightShiftContractError,
        match="cannot automatically mutate",
    ):
        RuntimeEvidenceValidationPolicy(
            automatic_matrix_mutation_enabled=True
        )


def test_duplicate_reviewer_identity_does_not_create_quorum() -> None:
    profiles = _concrete_profiles()
    acquisition = _acquisition(profiles)
    first, second, trust_set = _trust_fixture()
    first_review = sign_runtime_evidence_review(
        acquisition=acquisition,
        profile=profiles[0],
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        reviewer_signer=first,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="dbos:first:1",
    )
    duplicate = sign_runtime_evidence_review(
        acquisition=acquisition,
        profile=profiles[0],
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        reviewer_signer=first,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="dbos:first:2",
    )
    temporal_reviews = tuple(
        sign_runtime_evidence_review(
            acquisition=acquisition,
            profile=profiles[1],
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            reviewer_signer=signer,
            issued_at=NOW,
            expires_at=VALID_UNTIL,
            nonce=f"temporal:{signer.key_id}",
        )
        for signer in (first, second)
    )

    with pytest.raises(
        NightShiftContractError,
        match="reviewer identities must be unique",
    ):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=profiles,
            reviews=(first_review, duplicate) + temporal_reviews,
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            now_epoch=NOW,
            policy=RuntimeEvidenceValidationPolicy(),
        )


def test_tampered_review_signature_fails_closed() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)
    tampered_attestation = replace(
        reviews[0].attestation,
        signature_b64=base64.b64encode(bytes(64)).decode("ascii"),
    )
    tampered = replace(reviews[0], attestation=tampered_attestation)

    with pytest.raises(NightShiftContractError, match="signature invalid"):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=profiles,
            reviews=(tampered,) + reviews[1:],
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            now_epoch=NOW,
            policy=RuntimeEvidenceValidationPolicy(),
        )


def test_review_is_bound_to_exact_repository_sha() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)

    with pytest.raises(
        NightShiftContractError,
        match="repository SHA mismatch",
    ):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=profiles,
            reviews=reviews,
            subject_repo_sha="b" * 40,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            now_epoch=NOW,
            policy=RuntimeEvidenceValidationPolicy(),
        )


def test_expired_review_fails_closed() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)

    with pytest.raises(NightShiftContractError, match="attestation expired"):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=profiles,
            reviews=reviews,
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            now_epoch=VALID_UNTIL,
            policy=RuntimeEvidenceValidationPolicy(),
        )


def test_stale_profile_identity_fails_closed() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)
    stale_profiles = (
        replace(profiles[0], operational_rank=profiles[0].operational_rank + 1),
        profiles[1],
    )

    with pytest.raises(
        NightShiftContractError,
        match="candidate profile digest mismatch",
    ):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=stale_profiles,
            reviews=reviews,
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
            now_epoch=NOW,
            policy=RuntimeEvidenceValidationPolicy(),
        )


def test_result_digest_is_independent_of_input_order() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)
    policy = RuntimeEvidenceValidationPolicy()

    first = evaluate_runtime_evidence_validation(
        acquisition=acquisition,
        profiles=profiles,
        reviews=reviews,
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        now_epoch=NOW,
        policy=policy,
    )
    second = evaluate_runtime_evidence_validation(
        acquisition=acquisition,
        profiles=tuple(reversed(profiles)),
        reviews=tuple(reversed(reviews)),
        subject_repo_sha=REPO_SHA,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_identity=BUILDER_IDENTITY,
        now_epoch=NOW,
        policy=policy,
    )

    assert first.digest() == second.digest()


def test_wrong_pinned_trust_set_fails_closed() -> None:
    profiles = _concrete_profiles()
    acquisition, reviews, trust_set, _, _ = _signed_reviews(profiles)

    with pytest.raises(
        NightShiftContractError,
        match="trust-set identity mismatch",
    ):
        evaluate_runtime_evidence_validation(
            acquisition=acquisition,
            profiles=profiles,
            reviews=reviews,
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest="f" * 64,
            builder_identity=BUILDER_IDENTITY,
            now_epoch=NOW,
            policy=RuntimeEvidenceValidationPolicy(),
        )

def test_builder_cannot_self_certify_runtime_validation_review() -> None:
    profiles = _concrete_profiles()
    acquisition = _acquisition(profiles)
    first, _, trust_set = _trust_fixture()

    with pytest.raises(
        NightShiftContractError,
        match="builder cannot self-certify",
    ):
        sign_runtime_evidence_review(
            acquisition=acquisition,
            profile=profiles[0],
            subject_repo_sha=REPO_SHA,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            reviewer_signer=first,
            builder_identity=first.key_id,
            issued_at=NOW,
            expires_at=VALID_UNTIL,
            nonce="self-review-forbidden",
        )
