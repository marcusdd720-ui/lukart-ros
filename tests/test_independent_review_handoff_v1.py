from __future__ import annotations

import copy

import pytest

from core.crypto_agility_v1 import (
    CryptoKeyStatus,
    CryptoTrustKeyV1,
    CryptoTrustSetV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.independent_review_handoff_v1 import (
    IRH_EXTERNAL_REVIEW_STATUS,
    IRH_INDEPENDENCE_STATUS,
    IRH_INDEPENDENT_REVIEW_STATUS,
    IRH_VERIFIED_EVIDENCE_STATUS,
    ExternalReviewEvidenceV1,
    IndependentReviewHandoffError,
    IndependentReviewHandoffV1,
    ReviewArtifactIdentityV1,
    ReviewerOutcomeV1,
    ReviewerProvenanceV1,
    ReviewStatementV1,
    verify_external_review_evidence_v1,
)

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40
_PACKAGE_A = "1" * 64
_PACKAGE_B = "2" * 64
_REVIEW_BYTES = b"# External review\nSynthetic test artifact only.\n"


def _handoff(
    *,
    commit: str = _COMMIT_A,
    package_digest: str = _PACKAGE_A,
) -> IndependentReviewHandoffV1:
    return IndependentReviewHandoffV1.build(
        irr_source_commit_sha=commit,
        irr_package_name=f"IRR-01-v1-{commit}-{package_digest}.zip",
        irr_package_sha256=package_digest,
    )


def _trust(
    signer: AttestationSigner,
    *,
    status: CryptoKeyStatus = CryptoKeyStatus.ACTIVE,
    purposes: tuple[AttestationPurpose, ...] = (AttestationPurpose.SECURITY_REVIEW,),
) -> CryptoTrustSetV1:
    key = CryptoTrustKeyV1.from_public_key_bytes(
        key_id=signer.key_id,
        public_key=signer.public_key_bytes(),
        status=status,
        not_before=100,
        allowed_purposes=purposes,
    )
    return CryptoTrustSetV1(keys=(key,))


def _signed_evidence(
    signer: AttestationSigner,
    trust_set: CryptoTrustSetV1,
    *,
    handoff: IndependentReviewHandoffV1 | None = None,
    artifact_bytes: bytes = _REVIEW_BYTES,
    artifact_name: str = "review.md",
    outcome: ReviewerOutcomeV1 = ReviewerOutcomeV1.PASS,
    completed_at: int = 150,
    issued_at: int = 160,
    expires_at: int | None = None,
    reviewer_id: str | None = None,
) -> ExternalReviewEvidenceV1:
    selected_handoff = handoff or _handoff()
    reviewer = ReviewerProvenanceV1.build(
        reviewer_id=reviewer_id or signer.key_id,
        organization="External Review Fixture",
        role="Independent Reviewer Fixture",
    )
    artifact = ReviewArtifactIdentityV1.for_bytes(
        name=artifact_name,
        media_type="text/markdown",
        data=artifact_bytes,
    )
    statement = ReviewStatementV1.build(
        handoff=selected_handoff,
        reviewer=reviewer,
        artifact=artifact,
        outcome=outcome,
        review_completed_at=completed_at,
    )
    attestation = sign_attestation_v1(
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        signer=signer,
        purpose=AttestationPurpose.SECURITY_REVIEW,
        subject_digest=statement.statement_identity,
        payload=statement.canonical_body(),
        issued_at=issued_at,
        expires_at=expires_at,
        nonce="synthetic-review-fixture",
    )
    return ExternalReviewEvidenceV1.build(
        statement=statement,
        attestation=attestation,
    )


def test_handoff_is_deterministic_and_pending_only() -> None:
    first = _handoff()
    second = _handoff()

    assert first == second
    assert first.external_review_status == IRH_EXTERNAL_REVIEW_STATUS
    assert first.independent_review_status == IRH_INDEPENDENT_REVIEW_STATUS
    assert len(first.handoff_identity) == 64
    assert IndependentReviewHandoffV1.from_dict(first.canonical_dict()) == first


def test_valid_signed_external_evidence_is_verified_without_certification(
    tmp_path,
) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set)
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    result = verify_external_review_evidence_v1(
        expected_handoff=_handoff(),
        evidence=evidence,
        review_artifact_path=artifact_path,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        now=200,
    )

    assert result.evidence_status == IRH_VERIFIED_EVIDENCE_STATUS
    assert result.independence_status == IRH_INDEPENDENCE_STATUS
    assert result.independent_review_status == IRH_INDEPENDENT_REVIEW_STATUS
    assert result.reviewer_declared_outcome is ReviewerOutcomeV1.PASS
    assert result.automation_can_certify is False
    assert result.reviewer_id == signer.key_id
    assert len(result.crypto_verification_digest) == 64


def test_evidence_round_trip_is_strict_and_deterministic() -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set)

    restored = ExternalReviewEvidenceV1.from_dict(evidence.canonical_dict())

    assert restored == evidence
    assert restored.evidence_bundle_identity == evidence.evidence_bundle_identity


def test_cross_handoff_replay_is_rejected(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set, handoff=_handoff())
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="handoff mismatch"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(commit=_COMMIT_B, package_digest=_PACKAGE_B),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_tampered_review_artifact_is_rejected(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set)
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES + b"tampered")

    with pytest.raises(
        IndependentReviewHandoffError,
        match="size mismatch|SHA-256 mismatch",
    ):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_artifact_filename_substitution_is_rejected(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set)
    artifact_path = tmp_path / "other.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="filename mismatch"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_reviewer_identity_must_match_attestation_key(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(
        signer,
        trust_set,
        reviewer_id="different-reviewer-fixture",
    )
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="attestation key identity"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_untrusted_or_revoked_reviewer_key_fails_closed(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    active = _trust(signer)
    evidence = _signed_evidence(signer, active)
    revoked = _trust(signer, status=CryptoKeyStatus.REVOKED)
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="revoked"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=revoked,
            expected_trust_set_digest=revoked.trust_set_digest,
            now=200,
        )


def test_wrong_trust_set_identity_fails_closed(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(signer, trust_set)
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="identity mismatch"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest="f" * 64,
            now=200,
        )


def test_security_review_purpose_is_required(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(
        signer,
        purposes=(AttestationPurpose.PROVENANCE,),
    )
    handoff = _handoff()
    reviewer = ReviewerProvenanceV1.build(
        reviewer_id=signer.key_id,
        organization="External Review Fixture",
        role="Independent Reviewer Fixture",
    )
    artifact = ReviewArtifactIdentityV1.for_bytes(
        name="review.md",
        media_type="text/markdown",
        data=_REVIEW_BYTES,
    )
    statement = ReviewStatementV1.build(
        handoff=handoff,
        reviewer=reviewer,
        artifact=artifact,
        outcome=ReviewerOutcomeV1.ABSTAIN,
        review_completed_at=150,
    )
    attestation = sign_attestation_v1(
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        signer=signer,
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=statement.statement_identity,
        payload=statement.canonical_body(),
        issued_at=160,
        nonce="wrong-purpose-fixture",
    )
    evidence = ExternalReviewEvidenceV1.build(
        statement=statement,
        attestation=attestation,
    )
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="purpose"):
        verify_external_review_evidence_v1(
            expected_handoff=handoff,
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_expired_attestation_fails_closed(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(
        signer,
        trust_set,
        expires_at=180,
    )
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="expired"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_review_completion_must_precede_attestation_and_now(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(
        signer,
        trust_set,
        completed_at=170,
        issued_at=160,
    )
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    with pytest.raises(IndependentReviewHandoffError, match="after attestation issuance"):
        verify_external_review_evidence_v1(
            expected_handoff=_handoff(),
            evidence=evidence,
            review_artifact_path=artifact_path,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now=200,
        )


def test_forged_outcome_after_signature_is_rejected(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(
        signer,
        trust_set,
        outcome=ReviewerOutcomeV1.FAIL,
    )
    raw = copy.deepcopy(evidence.canonical_dict())
    statement = raw["statement"]
    assert isinstance(statement, dict)
    statement["outcome"] = ReviewerOutcomeV1.PASS.value

    with pytest.raises(IndependentReviewHandoffError, match="content-address mismatch"):
        ExternalReviewEvidenceV1.from_dict(raw)


def test_unknown_fields_and_path_traversal_fail_closed() -> None:
    raw = _handoff().canonical_dict()
    raw["future_authority"] = True
    with pytest.raises(IndependentReviewHandoffError, match="unknown=future_authority"):
        IndependentReviewHandoffV1.from_dict(raw)

    with pytest.raises(IndependentReviewHandoffError, match="safe basename"):
        ReviewArtifactIdentityV1.for_bytes(
            name="../review.md",
            media_type="text/markdown",
            data=_REVIEW_BYTES,
        )


def test_synthetic_test_signature_never_changes_repository_review_status(tmp_path) -> None:
    signer = AttestationSigner.generate("reviewer-fixture-a")
    trust_set = _trust(signer)
    evidence = _signed_evidence(
        signer,
        trust_set,
        outcome=ReviewerOutcomeV1.PASS_WITH_FINDINGS,
    )
    artifact_path = tmp_path / "review.md"
    artifact_path.write_bytes(_REVIEW_BYTES)

    result = verify_external_review_evidence_v1(
        expected_handoff=_handoff(),
        evidence=evidence,
        review_artifact_path=artifact_path,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        now=200,
    )

    assert result.independent_review_status == "NOT_INDEPENDENTLY_REVIEWED"
    assert result.automation_can_certify is False
