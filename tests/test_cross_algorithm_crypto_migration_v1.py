from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey

from core.cross_algorithm_crypto_migration_v1 import (
    ML_DSA_CONTEXT,
    CrossAlgorithmMigrationEnvelopeV1,
    CrossAlgorithmMigrationError,
    MigrationEvidenceState,
    Mldsa65AdapterProfileV1,
    Mldsa65MigrationKeyV1,
    measure_mldsa65_performance_v1,
    require_mldsa65_runtime_support_v1,
    sign_cross_algorithm_migration_v1,
    verify_cross_algorithm_migration_v1,
)
from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner, SignedAttestation

_SUBJECT = "a" * 64
_PAYLOAD = {"artifact": "archival-case-proof", "version": 1}


def _source(
    *,
    expires_at: int = 240,
) -> tuple[AttestationSigner, CryptoTrustSetV1, SignedAttestation]:
    signer = AttestationSigner.generate("ed25519-historical-a")
    trust_key = CryptoTrustKeyV1.from_public_key_bytes(
        key_id=signer.key_id,
        public_key=signer.public_key_bytes(),
        status=CryptoKeyStatus.ACTIVE,
        not_before=100,
        allowed_purposes=(AttestationPurpose.PROVENANCE,),
    )
    trust_set = CryptoTrustSetV1(keys=(trust_key,))
    attestation = signer.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        issued_at=120,
        expires_at=expires_at,
        nonce="historical-proof",
    )
    return signer, trust_set, attestation


def _migration_private_key() -> MLDSA65PrivateKey:
    return MLDSA65PrivateKey.from_seed_bytes(bytes(range(32)))


def _migration_key(
    *,
    source_key_id: str,
    private_key: MLDSA65PrivateKey,
    profile: Mldsa65AdapterProfileV1,
    status: CryptoKeyStatus = CryptoKeyStatus.ACTIVE,
    not_before: int = 180,
    retire_at: int | None = None,
) -> Mldsa65MigrationKeyV1:
    return Mldsa65MigrationKeyV1.from_public_key_bytes(
        key_id="mldsa65-archive-a",
        public_key=private_key.public_key().public_bytes_raw(),
        status=status,
        not_before=not_before,
        retire_at=retire_at,
        allowed_purposes=(AttestationPurpose.PROVENANCE,),
        predecessor_ed25519_key_id=source_key_id,
        adapter_profile_digest=profile.profile_digest,
    )


def _signed_migration(
    *,
    source_expires_at: int = 240,
) -> tuple[
    CryptoTrustSetV1,
    SignedAttestation,
    MLDSA65PrivateKey,
    Mldsa65MigrationKeyV1,
    Mldsa65AdapterProfileV1,
    CrossAlgorithmMigrationEnvelopeV1,
]:
    source_signer, source_trust_set, source_attestation = _source(
        expires_at=source_expires_at
    )
    profile = Mldsa65AdapterProfileV1()
    private_key = _migration_private_key()
    migration_key = _migration_key(
        source_key_id=source_signer.key_id,
        private_key=private_key,
        profile=profile,
    )
    envelope = sign_cross_algorithm_migration_v1(
        source_attestation=source_attestation,
        source_payload=_PAYLOAD,
        source_trust_set=source_trust_set,
        expected_source_trust_set_digest=source_trust_set.trust_set_digest,
        migration_key=migration_key,
        expected_migration_key_context_digest=migration_key.key_context_digest,
        adapter_profile=profile,
        expected_adapter_profile_digest=profile.profile_digest,
        private_key=private_key,
        issued_at=200,
        nonce="migration-proof",
    )
    return (
        source_trust_set,
        source_attestation,
        private_key,
        migration_key,
        profile,
        envelope,
    )


def _verify(
    source_trust_set: CryptoTrustSetV1,
    source_attestation: SignedAttestation,
    migration_key: Mldsa65MigrationKeyV1,
    profile: Mldsa65AdapterProfileV1,
    envelope: CrossAlgorithmMigrationEnvelopeV1,
    *,
    now: int = 220,
):
    return verify_cross_algorithm_migration_v1(
        envelope=envelope,
        source_attestation=source_attestation,
        source_payload=_PAYLOAD,
        source_trust_set=source_trust_set,
        expected_source_trust_set_digest=source_trust_set.trust_set_digest,
        migration_key=migration_key,
        expected_migration_key_context_digest=migration_key.key_context_digest,
        adapter_profile=profile,
        expected_adapter_profile_digest=profile.profile_digest,
        now=now,
    )


def test_runtime_support_and_fixed_profile_are_explicit() -> None:
    runtime = require_mldsa65_runtime_support_v1()
    profile = Mldsa65AdapterProfileV1()

    assert runtime.cryptography_version == profile.implementation_version
    assert profile.parameter_set == "ML-DSA-65"
    assert profile.standard_id == "NIST-FIPS-204"
    assert profile.fips_validation_claim is False
    assert profile.cross_implementation_interoperability_proven is False


def test_valid_source_is_additively_migrated_and_dual_verified() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration()
    )

    result = _verify(
        source_trust_set,
        source_attestation,
        migration_key,
        profile,
        envelope,
    )

    assert result.state is MigrationEvidenceState.DUAL_VERIFIED_ADDITIVE_EVIDENCE
    assert result.migration_key_material_digest == migration_key.key_material_digest
    assert result.migration_key_context_digest == migration_key.key_context_digest
    assert result.automation_can_promote_trust is False
    assert result.fips_validation_claim is False
    assert result.independent_crypto_review_claim is False
    assert len(result.verification_digest) == 64


def test_envelope_and_key_strict_round_trip_preserve_identity() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration()
    )

    restored_key = Mldsa65MigrationKeyV1.from_dict(migration_key.canonical_dict())
    restored_envelope = CrossAlgorithmMigrationEnvelopeV1.from_dict(
        envelope.canonical_dict()
    )

    assert restored_key == migration_key
    assert restored_envelope == envelope
    assert restored_envelope.envelope_digest == envelope.envelope_digest
    _verify(
        source_trust_set,
        source_attestation,
        restored_key,
        profile,
        restored_envelope,
    )


def test_unknown_serialized_fields_fail_closed() -> None:
    _, _, _, migration_key, _, envelope = _signed_migration()
    key_payload = copy.deepcopy(migration_key.canonical_dict())
    key_payload["unexpected"] = True
    envelope_payload = copy.deepcopy(envelope.canonical_dict())
    envelope_payload["unexpected"] = True

    with pytest.raises(CrossAlgorithmMigrationError, match="unknown=unexpected"):
        Mldsa65MigrationKeyV1.from_dict(key_payload)
    with pytest.raises(CrossAlgorithmMigrationError, match="unknown=unexpected"):
        CrossAlgorithmMigrationEnvelopeV1.from_dict(envelope_payload)


def test_source_payload_tampering_fails_before_migration_trust() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration()
    )

    with pytest.raises(ValueError, match="payload"):
        verify_cross_algorithm_migration_v1(
            envelope=envelope,
            source_attestation=source_attestation,
            source_payload={"artifact": "tampered", "version": 1},
            source_trust_set=source_trust_set,
            expected_source_trust_set_digest=source_trust_set.trust_set_digest,
            migration_key=migration_key,
            expected_migration_key_context_digest=migration_key.key_context_digest,
            adapter_profile=profile,
            expected_adapter_profile_digest=profile.profile_digest,
            now=220,
        )


def test_envelope_tampering_breaks_mldsa_signature() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration()
    )
    tampered = replace(envelope, nonce="migration-proof-tampered")

    with pytest.raises(CrossAlgorithmMigrationError, match="signature invalid"):
        _verify(
            source_trust_set,
            source_attestation,
            migration_key,
            profile,
            tampered,
        )


def test_context_is_domain_separated() -> None:
    _, _, _, migration_key, _, envelope = _signed_migration()
    signature = __import__("base64").b64decode(envelope.signature_b64)

    with pytest.raises(InvalidSignature):
        migration_key_public = migration_key.public_key_bytes()
        from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PublicKey

        MLDSA65PublicKey.from_public_bytes(migration_key_public).verify(
            signature,
            __import__("core.p3.contracts", fromlist=["canonical_json"])
            .canonical_json(envelope.canonical_body())
            .encode("utf-8"),
            ML_DSA_CONTEXT + b"-wrong",
        )


def test_wrong_migration_private_key_is_rejected() -> None:
    source_signer, source_trust_set, source_attestation = _source()
    profile = Mldsa65AdapterProfileV1()
    pinned_private = _migration_private_key()
    wrong_private = MLDSA65PrivateKey.from_seed_bytes(bytes(reversed(range(32))))
    migration_key = _migration_key(
        source_key_id=source_signer.key_id,
        private_key=pinned_private,
        profile=profile,
    )

    with pytest.raises(CrossAlgorithmMigrationError, match="does not match"):
        sign_cross_algorithm_migration_v1(
            source_attestation=source_attestation,
            source_payload=_PAYLOAD,
            source_trust_set=source_trust_set,
            expected_source_trust_set_digest=source_trust_set.trust_set_digest,
            migration_key=migration_key,
            expected_migration_key_context_digest=migration_key.key_context_digest,
            adapter_profile=profile,
            expected_adapter_profile_digest=profile.profile_digest,
            private_key=wrong_private,
            issued_at=200,
            nonce="wrong-key",
        )


def test_wrong_pinned_source_trust_set_fails_closed() -> None:
    source_trust_set, source_attestation, private_key, migration_key, profile, _ = (
        _signed_migration()
    )

    with pytest.raises(CrossAlgorithmMigrationError, match="source trust-set identity"):
        sign_cross_algorithm_migration_v1(
            source_attestation=source_attestation,
            source_payload=_PAYLOAD,
            source_trust_set=source_trust_set,
            expected_source_trust_set_digest="f" * 64,
            migration_key=migration_key,
            expected_migration_key_context_digest=migration_key.key_context_digest,
            adapter_profile=profile,
            expected_adapter_profile_digest=profile.profile_digest,
            private_key=private_key,
            issued_at=200,
            nonce="wrong-source-pin",
        )


def test_retirement_preserves_pre_retirement_migration_verification() -> None:
    source_trust_set, source_attestation, private_key, active_key, profile, envelope = (
        _signed_migration()
    )
    retired_key = _migration_key(
        source_key_id=source_attestation.key_id,
        private_key=private_key,
        profile=profile,
        status=CryptoKeyStatus.RETIRED,
        not_before=active_key.not_before,
        retire_at=210,
    )

    assert retired_key.key_material_digest == active_key.key_material_digest
    assert retired_key.key_context_digest != active_key.key_context_digest
    result = _verify(
        source_trust_set,
        source_attestation,
        retired_key,
        profile,
        envelope,
        now=300,
    )
    assert result.migration_key_context_digest == retired_key.key_context_digest


def test_revocation_rejects_previously_valid_migration() -> None:
    source_trust_set, source_attestation, private_key, active_key, profile, envelope = (
        _signed_migration()
    )
    revoked_key = _migration_key(
        source_key_id=source_attestation.key_id,
        private_key=private_key,
        profile=profile,
        status=CryptoKeyStatus.REVOKED,
        not_before=active_key.not_before,
    )

    assert revoked_key.key_material_digest == active_key.key_material_digest
    with pytest.raises(CrossAlgorithmMigrationError, match="revoked"):
        _verify(
            source_trust_set,
            source_attestation,
            revoked_key,
            profile,
            envelope,
            now=300,
        )


def test_source_may_expire_after_valid_migration_without_erasing_archival_proof() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration(source_expires_at=205)
    )

    result = _verify(
        source_trust_set,
        source_attestation,
        migration_key,
        profile,
        envelope,
        now=500,
    )

    assert result.state is MigrationEvidenceState.DUAL_VERIFIED_ADDITIVE_EVIDENCE


def test_source_expired_before_migration_is_rejected() -> None:
    source_signer, source_trust_set, source_attestation = _source(expires_at=190)
    profile = Mldsa65AdapterProfileV1()
    private_key = _migration_private_key()
    migration_key = _migration_key(
        source_key_id=source_signer.key_id,
        private_key=private_key,
        profile=profile,
    )

    with pytest.raises(ValueError, match="expired"):
        sign_cross_algorithm_migration_v1(
            source_attestation=source_attestation,
            source_payload=_PAYLOAD,
            source_trust_set=source_trust_set,
            expected_source_trust_set_digest=source_trust_set.trust_set_digest,
            migration_key=migration_key,
            expected_migration_key_context_digest=migration_key.key_context_digest,
            adapter_profile=profile,
            expected_adapter_profile_digest=profile.profile_digest,
            private_key=private_key,
            issued_at=200,
            nonce="expired-source",
        )


def test_future_envelope_is_rejected() -> None:
    source_trust_set, source_attestation, _, migration_key, profile, envelope = (
        _signed_migration()
    )

    with pytest.raises(CrossAlgorithmMigrationError, match="not yet valid"):
        _verify(
            source_trust_set,
            source_attestation,
            migration_key,
            profile,
            envelope,
            now=199,
        )


def test_adapter_profile_cannot_be_reinterpreted() -> None:
    with pytest.raises(CrossAlgorithmMigrationError, match="parameter_set"):
        Mldsa65AdapterProfileV1(parameter_set="ML-DSA-44")


def test_bounded_performance_probe_stays_within_operational_budget() -> None:
    report = measure_mldsa65_performance_v1(iterations=3)

    assert report["parameter_set"] == "ML-DSA-65"
    assert report["within_budget"] is True
