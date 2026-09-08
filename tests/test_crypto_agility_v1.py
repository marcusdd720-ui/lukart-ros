from __future__ import annotations

import copy

import pytest

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoKeyStatus,
    CryptoTrustKeyV1,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import AttestationPurpose, AttestationSigner

_SUBJECT = "a" * 64
_PAYLOAD = {"artifact": "case-bundle", "version": 1}


def _key(
    signer: AttestationSigner,
    *,
    status: CryptoKeyStatus = CryptoKeyStatus.ACTIVE,
    not_before: int = 100,
    retire_at: int | None = None,
    predecessor_key_id: str | None = None,
    purposes: tuple[AttestationPurpose, ...] = (AttestationPurpose.PROVENANCE,),
) -> CryptoTrustKeyV1:
    return CryptoTrustKeyV1.from_public_key_bytes(
        key_id=signer.key_id,
        public_key=signer.public_key_bytes(),
        status=status,
        not_before=not_before,
        retire_at=retire_at,
        predecessor_key_id=predecessor_key_id,
        allowed_purposes=purposes,
    )


def test_trust_set_identity_and_strict_round_trip_are_deterministic() -> None:
    signer = AttestationSigner.generate("exchange-2026-a")
    trust_set = CryptoTrustSetV1(keys=(_key(signer),))

    restored = CryptoTrustSetV1.from_dict(trust_set.canonical_dict())

    assert restored == trust_set
    assert restored.trust_set_digest == trust_set.trust_set_digest


def test_active_key_signs_and_verification_binds_exact_trust_set() -> None:
    signer = AttestationSigner.generate("exchange-2026-a")
    trust_set = CryptoTrustSetV1(keys=(_key(signer),))
    attestation = sign_attestation_v1(
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        signer=signer,
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        issued_at=120,
        expires_at=500,
        nonce="n-1",
    )

    result = CryptoTrustVerifierV1(
        trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
    ).verify(
        attestation,
        expected_purpose=AttestationPurpose.PROVENANCE,
        expected_subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        now=200,
    )

    assert result.trust_set_digest == trust_set.trust_set_digest
    assert result.key_digest == trust_set.keys[0].key_digest
    assert result.attestation_digest == attestation.digest()
    assert len(result.verification_digest) == 64


def test_planned_rotation_preserves_pre_retirement_offline_verification() -> None:
    old = AttestationSigner.generate("exchange-2026-a")
    new = AttestationSigner.generate("exchange-2027-b")
    historical = old.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        issued_at=150,
        expires_at=600,
        nonce="historical",
    )
    trust_set = CryptoTrustSetV1(
        keys=(
            _key(
                old,
                status=CryptoKeyStatus.RETIRED,
                retire_at=200,
            ),
            _key(
                new,
                not_before=200,
                predecessor_key_id=old.key_id,
            ),
        )
    )

    result = CryptoTrustVerifierV1(
        trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
    ).verify(
        historical,
        expected_purpose=AttestationPurpose.PROVENANCE,
        expected_subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        now=300,
    )

    assert result.attestation_digest == historical.digest()


def test_retired_key_cannot_issue_new_attestation() -> None:
    signer = AttestationSigner.generate("exchange-2026-a")
    trust_set = CryptoTrustSetV1(
        keys=(
            _key(
                signer,
                status=CryptoKeyStatus.RETIRED,
                retire_at=200,
            ),
        )
    )

    with pytest.raises(CryptoAgilityV1Error, match="only ACTIVE"):
        sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            signer=signer,
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=_SUBJECT,
            payload=_PAYLOAD,
            issued_at=150,
            nonce="forbidden",
        )


def test_revocation_rejects_even_a_cryptographically_valid_backdated_signature() -> None:
    signer = AttestationSigner.generate("compromised-key")
    trust_set = CryptoTrustSetV1(
        keys=(_key(signer, status=CryptoKeyStatus.REVOKED),)
    )
    backdated = signer.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=_SUBJECT,
        payload=_PAYLOAD,
        issued_at=120,
        expires_at=500,
        nonce="backdated",
    )

    with pytest.raises(CryptoAgilityV1Error, match="revoked"):
        CryptoTrustVerifierV1(
            trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
        ).verify(
            backdated,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=_SUBJECT,
            payload=_PAYLOAD,
            now=200,
        )


def test_wrong_externally_pinned_trust_set_fails_closed() -> None:
    signer = AttestationSigner.generate("exchange-2026-a")
    trust_set = CryptoTrustSetV1(keys=(_key(signer),))

    with pytest.raises(CryptoAgilityV1Error, match="identity mismatch"):
        CryptoTrustVerifierV1(
            trust_set,
            expected_trust_set_digest="f" * 64,
        )


def test_key_purpose_is_least_privilege() -> None:
    signer = AttestationSigner.generate("release-only")
    trust_set = CryptoTrustSetV1(
        keys=(
            _key(
                signer,
                purposes=(AttestationPurpose.RELEASE,),
            ),
        )
    )

    with pytest.raises(CryptoAgilityV1Error, match="purpose is not allowed"):
        sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            signer=signer,
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=_SUBJECT,
            payload=_PAYLOAD,
            issued_at=120,
            nonce="wrong-purpose",
        )


def test_signer_key_material_must_match_pinned_key_id() -> None:
    pinned = AttestationSigner.generate("shared-id")
    impostor = AttestationSigner.generate("shared-id")
    trust_set = CryptoTrustSetV1(keys=(_key(pinned),))

    with pytest.raises(CryptoAgilityV1Error, match="public key does not match"):
        sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            signer=impostor,
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=_SUBJECT,
            payload=_PAYLOAD,
            issued_at=120,
            nonce="impostor",
        )


def test_unknown_algorithm_and_unknown_fields_fail_closed() -> None:
    signer = AttestationSigner.generate("exchange-2026-a")
    key = _key(signer)
    raw = key.canonical_dict()
    raw["algorithm"] = "ML-DSA-65"

    with pytest.raises(CryptoAgilityV1Error, match="unknown crypto algorithm"):
        CryptoTrustKeyV1.from_dict(raw)

    trust_set = CryptoTrustSetV1(keys=(key,))
    trust_raw = copy.deepcopy(trust_set.canonical_dict())
    trust_raw["future_field"] = "not-accepted"
    with pytest.raises(CryptoAgilityV1Error, match="unknown=future_field"):
        CryptoTrustSetV1.from_dict(trust_raw)


def test_missing_or_invalid_rotation_predecessor_fails_closed() -> None:
    old = AttestationSigner.generate("old")
    new = AttestationSigner.generate("new")

    with pytest.raises(CryptoAgilityV1Error, match="predecessor is not present"):
        CryptoTrustSetV1(
            keys=(
                _key(
                    new,
                    not_before=200,
                    predecessor_key_id=old.key_id,
                ),
            )
        )

    with pytest.raises(CryptoAgilityV1Error, match="must predate successor"):
        CryptoTrustSetV1(
            keys=(
                _key(old, not_before=300),
                _key(
                    new,
                    not_before=200,
                    predecessor_key_id=old.key_id,
                ),
            )
        )
