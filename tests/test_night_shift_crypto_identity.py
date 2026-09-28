from __future__ import annotations

import base64
from dataclasses import replace

import pytest

from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.crypto_identity import (
    SignedVerificationBundle,
    VerificationCryptoContext,
    sign_execution_receipt,
    sign_verification_bundle,
    verify_execution_receipt_signature,
    verify_verification_bundle_signatures,
)
from core.night_shift.promotion import VerificationQuorum, quorum_from_bundle
from core.night_shift.receipts import ExecutionReceipt
from core.night_shift.verification import (
    VerificationBundle,
    VerificationEvidence,
    VerificationGate,
)
from core.p3.contracts import content_digest

SHA = "a" * 40
TASK = "b" * 64
NOW = 10
VALID_UNTIL = 100


def _trust_fixture() -> tuple[
    AttestationSigner,
    AttestationSigner,
    CryptoTrustSetV1,
]:
    builder = AttestationSigner.generate("builder-key")
    reviewer = AttestationSigner.generate("reviewer-key")
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
    return builder, reviewer, trust_set


def _bundle(
    builder_identity: str = "builder-key",
    reviewer_identity: str = "reviewer-key",
) -> VerificationBundle:
    evidence = tuple(
        VerificationEvidence(
            gate=gate,
            passed=True,
            subject_sha=SHA,
            task_capsule_digest=TASK,
            producer_identity=(
                reviewer_identity
                if gate is VerificationGate.INDEPENDENT_REVIEW
                else builder_identity
            ),
            observed_at_epoch=NOW,
            evidence_digest=content_digest(
                {"gate": gate.value, "subject_sha": SHA, "task": TASK}
            ),
            evidence_refs=(f"test:{gate.value}",),
        )
        for gate in VerificationGate
    )
    return VerificationBundle(
        subject_sha=SHA,
        task_capsule_digest=TASK,
        builder_identity=builder_identity,
        reviewer_identity=reviewer_identity,
        evidence=evidence,
    )


def _signed_fixture() -> tuple[
    VerificationBundle,
    VerificationQuorum,
    VerificationCryptoContext,
    AttestationSigner,
    AttestationSigner,
]:
    builder, reviewer, trust_set = _trust_fixture()
    bundle = _bundle(builder.key_id, reviewer.key_id)
    quorum = quorum_from_bundle(
        bundle,
        now_epoch=NOW,
        max_evidence_age_seconds=VALID_UNTIL - NOW,
    )
    signed = sign_verification_bundle(
        bundle=bundle,
        quorum_digest=quorum.digest(),
        evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        builder_signer=builder,
        reviewer_signer=reviewer,
        issued_at=NOW,
        nonce_prefix="crypto-test",
    )
    return (
        bundle,
        quorum,
        VerificationCryptoContext(
            bundle=bundle,
            signed=signed,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        ),
        builder,
        reviewer,
    )


def _receipt() -> ExecutionReceipt:
    return ExecutionReceipt(
        task_id="task-1",
        workflow_id="workflow-1",
        lease_id="lease-1",
        fencing_token=1,
        policy_digest="1" * 64,
        decision_digest="2" * 64,
        state_snapshot_digest="3" * 64,
        task_capsule_digest="4" * 64,
        authority_envelope_digest="5" * 64,
        authority_reservation_digest="6" * 64,
        environment_digest="7" * 64,
        verification_digest="8" * 64,
        input_sha="9" * 40,
        output_sha="a" * 40,
        diff_digest="b" * 64,
        final_state="CLOSED_PASS",
        evidence_refs=("test:receipt",),
    )


def test_verification_bundle_signatures_verify_under_pinned_trust_set() -> None:
    bundle, quorum, context, _, _ = _signed_fixture()

    verified = verify_verification_bundle_signatures(
        context=context,
        quorum_digest=quorum.digest(),
        evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
        now_epoch=NOW,
    )

    assert verified.bundle_digest == bundle.digest()
    assert verified.trust_set_digest == context.expected_trust_set_digest
    assert verified.builder_key_id == bundle.builder_identity
    assert verified.reviewer_key_id == bundle.reviewer_identity
    assert verified.valid_until_epoch == quorum.evidence_valid_until_epoch
    assert verified.digest()


def test_tampered_builder_signature_fails_closed() -> None:
    _, quorum, context, _, _ = _signed_fixture()
    tampered_attestation = replace(
        context.signed.builder_attestation,
        signature_b64=base64.b64encode(bytes(64)).decode("ascii"),
    )
    tampered = SignedVerificationBundle(
        trust_set_digest=context.signed.trust_set_digest,
        builder_attestation=tampered_attestation,
        reviewer_attestation=context.signed.reviewer_attestation,
    )
    tampered_context = VerificationCryptoContext(
        bundle=context.bundle,
        signed=tampered,
        trust_set=context.trust_set,
        expected_trust_set_digest=context.expected_trust_set_digest,
    )
    with pytest.raises(NightShiftContractError, match="signature invalid"):
        verify_verification_bundle_signatures(
            context=tampered_context,
            quorum_digest=quorum.digest(),
            evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
            now_epoch=NOW,
        )


def test_builder_signing_key_must_match_declared_identity() -> None:
    builder, reviewer, trust_set = _trust_fixture()
    bundle = _bundle("other-builder", reviewer.key_id)
    quorum = quorum_from_bundle(
        bundle,
        now_epoch=NOW,
        max_evidence_age_seconds=90,
    )
    with pytest.raises(NightShiftContractError, match="builder signing key"):
        sign_verification_bundle(
            bundle=bundle,
            quorum_digest=quorum.digest(),
            evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            builder_signer=builder,
            reviewer_signer=reviewer,
            issued_at=NOW,
            nonce_prefix="wrong-builder",
        )


def test_reviewer_key_without_security_review_purpose_cannot_sign() -> None:
    builder = AttestationSigner.generate("builder-key")
    reviewer = AttestationSigner.generate("reviewer-key")
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
                allowed_purposes=(AttestationPurpose.PROVENANCE,),
            ),
        )
    )
    bundle = _bundle(builder.key_id, reviewer.key_id)
    quorum = quorum_from_bundle(bundle, now_epoch=NOW, max_evidence_age_seconds=90)
    with pytest.raises(NightShiftContractError, match="purpose is not allowed"):
        sign_verification_bundle(
            bundle=bundle,
            quorum_digest=quorum.digest(),
            evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            builder_signer=builder,
            reviewer_signer=reviewer,
            issued_at=NOW,
            nonce_prefix="wrong-purpose",
        )


def test_wrong_pinned_trust_set_digest_fails_closed() -> None:
    _, _, context, _, _ = _signed_fixture()
    with pytest.raises(NightShiftContractError, match="trust-set identity mismatch"):
        VerificationCryptoContext(
            bundle=context.bundle,
            signed=context.signed,
            trust_set=context.trust_set,
            expected_trust_set_digest="f" * 64,
        )


def test_expired_verification_signature_fails_closed() -> None:
    _, quorum, context, _, _ = _signed_fixture()
    with pytest.raises(NightShiftContractError, match="attestation expired"):
        verify_verification_bundle_signatures(
            context=context,
            quorum_digest=quorum.digest(),
            evidence_valid_until_epoch=quorum.evidence_valid_until_epoch,
            now_epoch=quorum.evidence_valid_until_epoch,
        )


def test_signed_verification_serialization_contains_no_private_key_material() -> None:
    _, _, context, _, _ = _signed_fixture()
    serialized = repr(context.signed.canonical_dict()).lower()
    assert "private_key" not in serialized
    assert "private key" not in serialized


def test_execution_receipt_signature_verifies() -> None:
    _, _, context, builder, _ = _signed_fixture()
    receipt = _receipt()
    signed = sign_execution_receipt(
        receipt=receipt,
        trust_set=context.trust_set,
        expected_trust_set_digest=context.expected_trust_set_digest,
        signer=builder,
        signer_identity=builder.key_id,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="receipt-test",
    )
    verified = verify_execution_receipt_signature(
        receipt=receipt,
        signed_receipt=signed,
        trust_set=context.trust_set,
        expected_trust_set_digest=context.expected_trust_set_digest,
        expected_signer_identity=builder.key_id,
        now_epoch=NOW,
    )
    assert verified.attestation_digest == signed.attestation.digest()
    assert verified.trust_set_digest == context.expected_trust_set_digest


def test_tampered_execution_receipt_fails_closed() -> None:
    _, _, context, builder, _ = _signed_fixture()
    receipt = _receipt()
    signed = sign_execution_receipt(
        receipt=receipt,
        trust_set=context.trust_set,
        expected_trust_set_digest=context.expected_trust_set_digest,
        signer=builder,
        signer_identity=builder.key_id,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="receipt-test",
    )
    tampered = replace(receipt, diff_digest="c" * 64)
    with pytest.raises(NightShiftContractError, match="subject mismatch|payload mismatch"):
        verify_execution_receipt_signature(
            receipt=tampered,
            signed_receipt=signed,
            trust_set=context.trust_set,
            expected_trust_set_digest=context.expected_trust_set_digest,
            expected_signer_identity=builder.key_id,
            now_epoch=NOW,
        )


def test_wrong_receipt_signer_identity_fails_closed() -> None:
    _, _, context, builder, _ = _signed_fixture()
    receipt = _receipt()
    signed = sign_execution_receipt(
        receipt=receipt,
        trust_set=context.trust_set,
        expected_trust_set_digest=context.expected_trust_set_digest,
        signer=builder,
        signer_identity=builder.key_id,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="receipt-test",
    )
    with pytest.raises(NightShiftContractError, match="signer identity mismatch"):
        verify_execution_receipt_signature(
            receipt=receipt,
            signed_receipt=signed,
            trust_set=context.trust_set,
            expected_trust_set_digest=context.expected_trust_set_digest,
            expected_signer_identity="other-signer",
            now_epoch=NOW,
        )
