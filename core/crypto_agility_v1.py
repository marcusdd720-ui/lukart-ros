"""CRY-01 crypto-agility, trust-set and key-lifecycle contract v1.

This module adds a versioned trust context around the existing Enterprise Ed25519
attestation primitive. It does not introduce a second signature implementation, store
private key material, promote Product truth, or claim post-quantum support.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.enterprise.contracts import (
    AttestationPurpose,
    AttestationSigner,
    AttestationVerifier,
    EnterpriseContractError,
    SignedAttestation,
)
from core.p3.contracts import content_digest, require_hex_digest

CRYPTO_TRUST_KEY_SCHEMA_V1 = "lukart.crypto-trust-key.v1"
CRYPTO_TRUST_SET_SCHEMA_V1 = "lukart.crypto-trust-set.v1"
CRYPTO_VERIFICATION_SCHEMA_V1 = "lukart.crypto-verification.v1"

_KEY_FIELDS = frozenset(
    {
        "schema",
        "key_id",
        "algorithm",
        "public_key_b64",
        "status",
        "not_before",
        "retire_at",
        "predecessor_key_id",
        "allowed_purposes",
    }
)
_TRUST_SET_FIELDS = frozenset(
    {"schema", "keys", "previous_trust_set_digest", "trust_set_digest"}
)


class CryptoAgilityV1Error(ValueError):
    """Fail-closed CRY-01 contract violation."""


class CryptoAlgorithmV1(StrEnum):
    ED25519 = "ED25519"


class CryptoKeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CryptoAgilityV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CryptoAgilityV1Error(f"{field_name} must be a nonnegative integer")
    return value


def _exact_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual))
    unknown = ",".join(sorted(actual - expected))
    details = []
    if missing:
        details.append(f"missing={missing}")
    if unknown:
        details.append(f"unknown={unknown}")
    raise CryptoAgilityV1Error(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


def _decode_public_key(value: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CryptoAgilityV1Error("public key must be canonical base64") from exc
    if len(raw) != 32:
        raise CryptoAgilityV1Error("ED25519 public key must be exactly 32 bytes")
    if base64.b64encode(raw).decode("ascii") != value:
        raise CryptoAgilityV1Error("public key base64 is not canonical")
    return raw


@dataclass(frozen=True, slots=True)
class CryptoTrustKeyV1:
    key_id: str
    algorithm: CryptoAlgorithmV1
    public_key_b64: str
    status: CryptoKeyStatus
    not_before: int
    allowed_purposes: tuple[AttestationPurpose, ...]
    retire_at: int | None = None
    predecessor_key_id: str | None = None
    schema: str = CRYPTO_TRUST_KEY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRYPTO_TRUST_KEY_SCHEMA_V1:
            raise CryptoAgilityV1Error(f"unsupported crypto key schema: {self.schema}")
        if not isinstance(self.algorithm, CryptoAlgorithmV1):
            raise CryptoAgilityV1Error("unknown or unsupported crypto algorithm")
        if not isinstance(self.status, CryptoKeyStatus):
            raise CryptoAgilityV1Error("unknown key lifecycle status")
        key_id = _text(self.key_id, field_name="key_id")
        public_key_b64 = _text(self.public_key_b64, field_name="public_key_b64")
        _decode_public_key(public_key_b64)
        not_before = _int(self.not_before, field_name="not_before")
        retire_at = self.retire_at
        if retire_at is not None:
            retire_at = _int(retire_at, field_name="retire_at")
            if retire_at <= not_before:
                raise CryptoAgilityV1Error("retire_at must be after not_before")
        if self.status is CryptoKeyStatus.RETIRED and retire_at is None:
            raise CryptoAgilityV1Error("RETIRED key requires retire_at")
        predecessor = self.predecessor_key_id
        if predecessor is not None:
            predecessor = _text(predecessor, field_name="predecessor_key_id")
            if predecessor == key_id:
                raise CryptoAgilityV1Error("key cannot be its own predecessor")
        if not self.allowed_purposes:
            raise CryptoAgilityV1Error("allowed_purposes cannot be empty")
        if any(not isinstance(item, AttestationPurpose) for item in self.allowed_purposes):
            raise CryptoAgilityV1Error("allowed_purposes contains unknown purpose")
        purposes = tuple(sorted(set(self.allowed_purposes), key=lambda item: item.value))
        object.__setattr__(self, "key_id", key_id)
        object.__setattr__(self, "public_key_b64", public_key_b64)
        object.__setattr__(self, "not_before", not_before)
        object.__setattr__(self, "retire_at", retire_at)
        object.__setattr__(self, "predecessor_key_id", predecessor)
        object.__setattr__(self, "allowed_purposes", purposes)

    @classmethod
    def from_public_key_bytes(
        cls,
        *,
        key_id: str,
        public_key: bytes,
        status: CryptoKeyStatus,
        not_before: int,
        allowed_purposes: Sequence[AttestationPurpose],
        retire_at: int | None = None,
        predecessor_key_id: str | None = None,
    ) -> CryptoTrustKeyV1:
        return cls(
            key_id=key_id,
            algorithm=CryptoAlgorithmV1.ED25519,
            public_key_b64=base64.b64encode(public_key).decode("ascii"),
            status=status,
            not_before=not_before,
            allowed_purposes=tuple(allowed_purposes),
            retire_at=retire_at,
            predecessor_key_id=predecessor_key_id,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CryptoTrustKeyV1:
        _exact_keys(value, expected=_KEY_FIELDS, field_name="crypto trust key")
        try:
            algorithm = CryptoAlgorithmV1(_text(value.get("algorithm"), field_name="algorithm"))
            status = CryptoKeyStatus(_text(value.get("status"), field_name="status"))
        except ValueError as exc:
            raise CryptoAgilityV1Error("unknown crypto algorithm or key status") from exc
        raw_purposes = value.get("allowed_purposes")
        if not isinstance(raw_purposes, list) or not raw_purposes:
            raise CryptoAgilityV1Error("allowed_purposes must be a nonempty list")
        try:
            purposes = tuple(
                AttestationPurpose(_text(item, field_name="allowed_purpose"))
                for item in raw_purposes
            )
        except ValueError as exc:
            raise CryptoAgilityV1Error("unknown attestation purpose") from exc
        retire_at_raw = value.get("retire_at")
        retire_at = (
            None
            if retire_at_raw is None
            else _int(retire_at_raw, field_name="retire_at")
        )
        predecessor_raw = value.get("predecessor_key_id")
        predecessor = (
            None
            if predecessor_raw is None
            else _text(predecessor_raw, field_name="predecessor_key_id")
        )
        return cls(
            key_id=_text(value.get("key_id"), field_name="key_id"),
            algorithm=algorithm,
            public_key_b64=_text(value.get("public_key_b64"), field_name="public_key_b64"),
            status=status,
            not_before=_int(value.get("not_before"), field_name="not_before"),
            allowed_purposes=purposes,
            retire_at=retire_at,
            predecessor_key_id=predecessor,
            schema=_text(value.get("schema"), field_name="key schema"),
        )

    def public_key_bytes(self) -> bytes:
        return _decode_public_key(self.public_key_b64)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "key_id": self.key_id,
            "algorithm": self.algorithm.value,
            "public_key_b64": self.public_key_b64,
            "status": self.status.value,
            "not_before": self.not_before,
            "retire_at": self.retire_at,
            "predecessor_key_id": self.predecessor_key_id,
            "allowed_purposes": [item.value for item in self.allowed_purposes],
        }

    @property
    def key_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CryptoTrustSetV1:
    keys: tuple[CryptoTrustKeyV1, ...]
    previous_trust_set_digest: str | None = None
    schema: str = CRYPTO_TRUST_SET_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRYPTO_TRUST_SET_SCHEMA_V1:
            raise CryptoAgilityV1Error(
                f"unsupported crypto trust-set schema: {self.schema}"
            )
        if not self.keys:
            raise CryptoAgilityV1Error("crypto trust set cannot be empty")
        ordered = tuple(sorted(self.keys, key=lambda item: item.key_id))
        ids = [item.key_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise CryptoAgilityV1Error("duplicate crypto key_id")
        known = {item.key_id: item for item in ordered}
        for item in ordered:
            predecessor = item.predecessor_key_id
            if predecessor is None:
                continue
            previous = known.get(predecessor)
            if previous is None:
                raise CryptoAgilityV1Error("key predecessor is not present in trust set")
            if previous.not_before >= item.not_before:
                raise CryptoAgilityV1Error("key predecessor must predate successor")
        previous_digest = self.previous_trust_set_digest
        if previous_digest is not None:
            try:
                previous_digest = require_hex_digest(
                    previous_digest,
                    field_name="previous_trust_set_digest",
                )
            except ValueError as exc:
                raise CryptoAgilityV1Error(str(exc)) from exc
        object.__setattr__(self, "keys", ordered)
        object.__setattr__(self, "previous_trust_set_digest", previous_digest)

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CryptoTrustSetV1:
        _exact_keys(value, expected=_TRUST_SET_FIELDS, field_name="crypto trust set")
        raw_keys = value.get("keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise CryptoAgilityV1Error("crypto trust-set keys must be a nonempty list")
        keys: list[CryptoTrustKeyV1] = []
        for raw in raw_keys:
            if not isinstance(raw, Mapping):
                raise CryptoAgilityV1Error("crypto trust-set key must be an object")
            keys.append(CryptoTrustKeyV1.from_dict(raw))
        previous_raw = value.get("previous_trust_set_digest")
        previous = (
            None
            if previous_raw is None
            else _text(previous_raw, field_name="previous_trust_set_digest")
        )
        trust_set = cls(
            keys=tuple(keys),
            previous_trust_set_digest=previous,
            schema=_text(value.get("schema"), field_name="trust-set schema"),
        )
        try:
            recorded = require_hex_digest(
                _text(value.get("trust_set_digest"), field_name="trust_set_digest"),
                field_name="trust_set_digest",
            )
        except ValueError as exc:
            raise CryptoAgilityV1Error(str(exc)) from exc
        if recorded != trust_set.trust_set_digest:
            raise CryptoAgilityV1Error("crypto trust-set digest mismatch")
        return trust_set

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "keys": [item.canonical_dict() for item in self.keys],
            "previous_trust_set_digest": self.previous_trust_set_digest,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "trust_set_digest": self.trust_set_digest}

    @property
    def trust_set_digest(self) -> str:
        return content_digest(self.canonical_body())

    def key(self, key_id: str) -> CryptoTrustKeyV1:
        normalized = _text(key_id, field_name="key_id")
        for item in self.keys:
            if item.key_id == normalized:
                return item
        raise CryptoAgilityV1Error("attestation key is not present in crypto trust set")


@dataclass(frozen=True, slots=True)
class CryptoVerificationV1:
    attestation_digest: str
    trust_set_digest: str
    key_digest: str
    algorithm: CryptoAlgorithmV1
    schema: str = CRYPTO_VERIFICATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRYPTO_VERIFICATION_SCHEMA_V1:
            raise CryptoAgilityV1Error(
                f"unsupported crypto verification schema: {self.schema}"
            )
        for field_name in ("attestation_digest", "trust_set_digest", "key_digest"):
            try:
                normalized = require_hex_digest(
                    getattr(self, field_name),
                    field_name=field_name,
                )
            except ValueError as exc:
                raise CryptoAgilityV1Error(str(exc)) from exc
            object.__setattr__(self, field_name, normalized)
        if not isinstance(self.algorithm, CryptoAlgorithmV1):
            raise CryptoAgilityV1Error("unknown crypto verification algorithm")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "attestation_digest": self.attestation_digest,
            "trust_set_digest": self.trust_set_digest,
            "key_digest": self.key_digest,
            "algorithm": self.algorithm.value,
        }

    @property
    def verification_digest(self) -> str:
        return content_digest(self.canonical_dict())


class CryptoTrustVerifierV1:
    """Verify Enterprise attestations under one externally pinned trust-set identity."""

    def __init__(
        self,
        trust_set: CryptoTrustSetV1,
        *,
        expected_trust_set_digest: str,
    ) -> None:
        try:
            expected = require_hex_digest(
                expected_trust_set_digest,
                field_name="expected_trust_set_digest",
            )
        except ValueError as exc:
            raise CryptoAgilityV1Error(str(exc)) from exc
        if trust_set.trust_set_digest != expected:
            raise CryptoAgilityV1Error("crypto trust-set identity mismatch")
        self._trust_set = trust_set
        self._trust_set_digest = expected

    def verify(
        self,
        attestation: SignedAttestation,
        *,
        expected_purpose: AttestationPurpose,
        expected_subject_digest: str,
        payload: Mapping[str, object],
        now: int,
    ) -> CryptoVerificationV1:
        key = self._trust_set.key(attestation.key_id)
        if key.algorithm is not CryptoAlgorithmV1.ED25519:
            raise CryptoAgilityV1Error("crypto algorithm adapter is not implemented")
        if expected_purpose not in key.allowed_purposes:
            raise CryptoAgilityV1Error("attestation purpose is not allowed for crypto key")
        if key.status is CryptoKeyStatus.REVOKED:
            raise CryptoAgilityV1Error("crypto key is revoked")
        if attestation.issued_at < key.not_before:
            raise CryptoAgilityV1Error("attestation predates crypto key activation")
        if key.retire_at is not None and attestation.issued_at >= key.retire_at:
            raise CryptoAgilityV1Error("attestation was issued after crypto key retirement")
        try:
            attestation_digest = AttestationVerifier(
                {key.key_id: key.public_key_bytes()}
            ).verify(
                attestation,
                expected_purpose=expected_purpose,
                expected_subject_digest=expected_subject_digest,
                payload=payload,
                now=now,
            )
        except EnterpriseContractError as exc:
            raise CryptoAgilityV1Error(str(exc)) from exc
        return CryptoVerificationV1(
            attestation_digest=attestation_digest,
            trust_set_digest=self._trust_set_digest,
            key_digest=key.key_digest,
            algorithm=key.algorithm,
        )


def sign_attestation_v1(
    *,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    signer: AttestationSigner,
    purpose: AttestationPurpose,
    subject_digest: str,
    payload: Mapping[str, object],
    issued_at: int,
    expires_at: int | None = None,
    nonce: str,
) -> SignedAttestation:
    """Sign only with an active key bound to the externally pinned trust-set identity."""

    CryptoTrustVerifierV1(
        trust_set,
        expected_trust_set_digest=expected_trust_set_digest,
    )
    key = trust_set.key(signer.key_id)
    if key.status is not CryptoKeyStatus.ACTIVE:
        raise CryptoAgilityV1Error("only ACTIVE crypto key may sign new attestations")
    if purpose not in key.allowed_purposes:
        raise CryptoAgilityV1Error("attestation purpose is not allowed for crypto key")
    if issued_at < key.not_before:
        raise CryptoAgilityV1Error("cannot sign before crypto key activation")
    if key.retire_at is not None and issued_at >= key.retire_at:
        raise CryptoAgilityV1Error("cannot sign at or after crypto key retirement")
    if signer.public_key_bytes() != key.public_key_bytes():
        raise CryptoAgilityV1Error("signer public key does not match crypto trust-set key")
    try:
        return signer.sign(
            purpose=purpose,
            subject_digest=subject_digest,
            payload=payload,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
    except EnterpriseContractError as exc:
        raise CryptoAgilityV1Error(str(exc)) from exc
