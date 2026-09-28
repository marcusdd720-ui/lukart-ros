"""Cryptographic automation identity bindings for Night Shift V2-10."""

from __future__ import annotations

from dataclasses import dataclass

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
    CryptoVerificationV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import (
    AttestationPurpose,
    AttestationSigner,
    SignedAttestation,
)
from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .receipts import ExecutionReceipt
from .verification import VerificationBundle

VERIFICATION_SIGNATURE_SCHEMA = "night-shift-verification-signature/v1"
RECEIPT_SIGNATURE_SCHEMA = "night-shift-receipt-signature/v1"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


def _attestation_dict(attestation: SignedAttestation) -> dict[str, object]:
    return {
        **attestation.canonical_body(),
        "signature_b64": attestation.signature_b64,
    }


@dataclass(frozen=True, slots=True)
class SignedVerificationBundle:
    trust_set_digest: str
    builder_attestation: SignedAttestation
    reviewer_attestation: SignedAttestation

    def __post_init__(self) -> None:
        trust = _digest(self.trust_set_digest, field_name="trust_set_digest")
        if self.builder_attestation.key_id == self.reviewer_attestation.key_id:
            raise NightShiftContractError(
                "builder and reviewer cryptographic identities must differ"
            )
        object.__setattr__(self, "trust_set_digest", trust)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": VERIFICATION_SIGNATURE_SCHEMA,
            "trust_set_digest": self.trust_set_digest,
            "builder_attestation": _attestation_dict(self.builder_attestation),
            "reviewer_attestation": _attestation_dict(self.reviewer_attestation),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class VerificationCryptoContext:
    bundle: VerificationBundle
    signed: SignedVerificationBundle
    trust_set: CryptoTrustSetV1
    expected_trust_set_digest: str

    def __post_init__(self) -> None:
        expected = _digest(
            self.expected_trust_set_digest,
            field_name="expected_trust_set_digest",
        )
        if self.signed.trust_set_digest != expected:
            raise NightShiftContractError(
                "signed verification trust-set identity mismatch"
            )
        object.__setattr__(self, "expected_trust_set_digest", expected)


@dataclass(frozen=True, slots=True)
class VerifiedVerificationSignatures:
    bundle_digest: str
    trust_set_digest: str
    builder_key_id: str
    reviewer_key_id: str
    builder_verification_digest: str
    reviewer_verification_digest: str
    valid_until_epoch: int

    def __post_init__(self) -> None:
        for name in (
            "bundle_digest",
            "trust_set_digest",
            "builder_verification_digest",
            "reviewer_verification_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        if not self.builder_key_id.strip() or not self.reviewer_key_id.strip():
            raise NightShiftContractError("cryptographic key identities are required")
        if self.builder_key_id == self.reviewer_key_id:
            raise NightShiftContractError(
                "builder and reviewer cryptographic identities must differ"
            )
        if self.valid_until_epoch < 0:
            raise NightShiftContractError(
                "cryptographic verification expiry cannot be negative"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": VERIFICATION_SIGNATURE_SCHEMA,
            "bundle_digest": self.bundle_digest,
            "trust_set_digest": self.trust_set_digest,
            "builder_key_id": self.builder_key_id,
            "reviewer_key_id": self.reviewer_key_id,
            "builder_verification_digest": self.builder_verification_digest,
            "reviewer_verification_digest": self.reviewer_verification_digest,
            "valid_until_epoch": self.valid_until_epoch,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class SignedExecutionReceipt:
    trust_set_digest: str
    signer_identity: str
    attestation: SignedAttestation

    def __post_init__(self) -> None:
        trust = _digest(self.trust_set_digest, field_name="trust_set_digest")
        signer = self.signer_identity.strip()
        if not signer:
            raise NightShiftContractError("receipt signer identity is required")
        if self.attestation.key_id != signer:
            raise NightShiftContractError(
                "receipt attestation key does not match signer identity"
            )
        object.__setattr__(self, "trust_set_digest", trust)
        object.__setattr__(self, "signer_identity", signer)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_SIGNATURE_SCHEMA,
            "trust_set_digest": self.trust_set_digest,
            "signer_identity": self.signer_identity,
            "attestation": _attestation_dict(self.attestation),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CanaryCryptographicContext:
    verification: VerificationCryptoContext
    receipt_signer: AttestationSigner
    receipt_signer_identity: str

    def __post_init__(self) -> None:
        identity = self.receipt_signer_identity.strip()
        if not identity:
            raise NightShiftContractError("receipt signer identity is required")
        if self.receipt_signer.key_id != identity:
            raise NightShiftContractError(
                "receipt signer key does not match declared identity"
            )
        object.__setattr__(self, "receipt_signer_identity", identity)


def _verification_payload(
    bundle: VerificationBundle,
    *,
    role: str,
    identity: str,
    quorum_digest: str,
    evidence_valid_until_epoch: int,
) -> dict[str, object]:
    return {
        "schema": VERIFICATION_SIGNATURE_SCHEMA,
        "artifact": "verification_bundle",
        "role": role,
        "identity": identity,
        "bundle_digest": bundle.digest(),
        "quorum_digest": _digest(quorum_digest, field_name="quorum_digest"),
        "subject_sha": bundle.subject_sha,
        "task_capsule_digest": bundle.task_capsule_digest,
        "evidence_valid_until_epoch": evidence_valid_until_epoch,
    }


def sign_verification_bundle(
    *,
    bundle: VerificationBundle,
    quorum_digest: str,
    evidence_valid_until_epoch: int,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    builder_signer: AttestationSigner,
    reviewer_signer: AttestationSigner,
    issued_at: int,
    nonce_prefix: str,
) -> SignedVerificationBundle:
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError("crypto trust-set identity mismatch")
    if builder_signer.key_id != bundle.builder_identity:
        raise NightShiftContractError(
            "builder signing key does not match declared builder identity"
        )
    if reviewer_signer.key_id != bundle.reviewer_identity:
        raise NightShiftContractError(
            "reviewer signing key does not match declared reviewer identity"
        )
    if issued_at >= evidence_valid_until_epoch:
        raise NightShiftContractError(
            "cannot sign verification bundle at or after evidence expiry"
        )
    nonce = nonce_prefix.strip()
    if not nonce:
        raise NightShiftContractError("verification signature nonce prefix is required")

    builder_payload = _verification_payload(
        bundle,
        role="builder",
        identity=bundle.builder_identity,
        quorum_digest=quorum_digest,
        evidence_valid_until_epoch=evidence_valid_until_epoch,
    )
    reviewer_payload = _verification_payload(
        bundle,
        role="reviewer",
        identity=bundle.reviewer_identity,
        quorum_digest=quorum_digest,
        evidence_valid_until_epoch=evidence_valid_until_epoch,
    )
    try:
        builder = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected,
            signer=builder_signer,
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=bundle.digest(),
            payload=builder_payload,
            issued_at=issued_at,
            expires_at=evidence_valid_until_epoch,
            nonce=f"{nonce}:builder",
        )
        reviewer = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected,
            signer=reviewer_signer,
            purpose=AttestationPurpose.SECURITY_REVIEW,
            subject_digest=bundle.digest(),
            payload=reviewer_payload,
            issued_at=issued_at,
            expires_at=evidence_valid_until_epoch,
            nonce=f"{nonce}:reviewer",
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return SignedVerificationBundle(expected, builder, reviewer)


def verify_verification_bundle_signatures(
    *,
    context: VerificationCryptoContext,
    quorum_digest: str,
    evidence_valid_until_epoch: int,
    now_epoch: int,
) -> VerifiedVerificationSignatures:
    bundle = context.bundle
    signed = context.signed
    if signed.builder_attestation.key_id != bundle.builder_identity:
        raise NightShiftContractError(
            "builder attestation key does not match declared builder identity"
        )
    if signed.reviewer_attestation.key_id != bundle.reviewer_identity:
        raise NightShiftContractError(
            "reviewer attestation key does not match declared reviewer identity"
        )
    if (
        signed.builder_attestation.expires_at != evidence_valid_until_epoch
        or signed.reviewer_attestation.expires_at != evidence_valid_until_epoch
    ):
        raise NightShiftContractError(
            "verification signature expiry does not match evidence lifetime"
        )

    builder_payload = _verification_payload(
        bundle,
        role="builder",
        identity=bundle.builder_identity,
        quorum_digest=quorum_digest,
        evidence_valid_until_epoch=evidence_valid_until_epoch,
    )
    reviewer_payload = _verification_payload(
        bundle,
        role="reviewer",
        identity=bundle.reviewer_identity,
        quorum_digest=quorum_digest,
        evidence_valid_until_epoch=evidence_valid_until_epoch,
    )
    try:
        verifier = CryptoTrustVerifierV1(
            context.trust_set,
            expected_trust_set_digest=context.expected_trust_set_digest,
        )
        builder = verifier.verify(
            signed.builder_attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=bundle.digest(),
            payload=builder_payload,
            now=now_epoch,
        )
        reviewer = verifier.verify(
            signed.reviewer_attestation,
            expected_purpose=AttestationPurpose.SECURITY_REVIEW,
            expected_subject_digest=bundle.digest(),
            payload=reviewer_payload,
            now=now_epoch,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return VerifiedVerificationSignatures(
        bundle_digest=bundle.digest(),
        trust_set_digest=context.expected_trust_set_digest,
        builder_key_id=bundle.builder_identity,
        reviewer_key_id=bundle.reviewer_identity,
        builder_verification_digest=builder.verification_digest,
        reviewer_verification_digest=reviewer.verification_digest,
        valid_until_epoch=evidence_valid_until_epoch,
    )


def _receipt_payload(receipt: ExecutionReceipt) -> dict[str, object]:
    return {
        "schema": RECEIPT_SIGNATURE_SCHEMA,
        "artifact": "execution_receipt",
        "receipt_digest": receipt.digest(),
        "receipt": receipt.canonical_dict(),
    }


def sign_execution_receipt(
    *,
    receipt: ExecutionReceipt,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    signer: AttestationSigner,
    signer_identity: str,
    issued_at: int,
    expires_at: int,
    nonce: str,
) -> SignedExecutionReceipt:
    identity = signer_identity.strip()
    if signer.key_id != identity:
        raise NightShiftContractError(
            "receipt signer key does not match declared identity"
        )
    if issued_at >= expires_at:
        raise NightShiftContractError(
            "cannot sign execution receipt at or after signature expiry"
        )
    try:
        attestation = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected_trust_set_digest,
            signer=signer,
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=receipt.digest(),
            payload=_receipt_payload(receipt),
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return SignedExecutionReceipt(
        trust_set_digest=expected_trust_set_digest,
        signer_identity=identity,
        attestation=attestation,
    )


def verify_execution_receipt_signature(
    *,
    receipt: ExecutionReceipt,
    signed_receipt: SignedExecutionReceipt,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    expected_signer_identity: str,
    now_epoch: int,
) -> CryptoVerificationV1:
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    identity = expected_signer_identity.strip()
    if signed_receipt.trust_set_digest != expected:
        raise NightShiftContractError("receipt trust-set identity mismatch")
    if signed_receipt.signer_identity != identity:
        raise NightShiftContractError("receipt signer identity mismatch")
    if signed_receipt.attestation.key_id != identity:
        raise NightShiftContractError("receipt attestation key identity mismatch")
    try:
        return CryptoTrustVerifierV1(
            trust_set,
            expected_trust_set_digest=expected,
        ).verify(
            signed_receipt.attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=receipt.digest(),
            payload=_receipt_payload(receipt),
            now=now_epoch,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
