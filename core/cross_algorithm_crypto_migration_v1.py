"""LRD-01J additive Ed25519 -> ML-DSA-65 migration evidence v1.

The closed CRY-01 Ed25519 contract remains authoritative for historical attestations.
This module adds a separately pinned ML-DSA-65 verification context and migration
envelope. It does not modify CRY-01, persist private keys, promote trust, mutate the
Canonical Case Ledger, publish releases, or claim FIPS validation/certification.
"""

from __future__ import annotations

import base64
import binascii
import platform
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import cryptography
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.backends.openssl import backend as openssl_backend
from cryptography.hazmat.primitives.asymmetric.mldsa import (
    MLDSA65PrivateKey,
    MLDSA65PublicKey,
)

from core.crypto_agility_v1 import (
    CryptoKeyStatus,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
)
from core.enterprise.contracts import AttestationPurpose, SignedAttestation
from core.p3.contracts import canonical_json, content_digest, require_hex_digest

ADAPTER_PROFILE_SCHEMA_V1 = "lukart.lrd-cross-algorithm-adapter-profile.v1"
RUNTIME_PROVENANCE_SCHEMA_V1 = "lukart.lrd-cross-algorithm-runtime-provenance.v1"
MIGRATION_KEY_SCHEMA_V1 = "lukart.lrd-cross-algorithm-key.v1"
MIGRATION_ENVELOPE_SCHEMA_V1 = "lukart.lrd-cross-algorithm-envelope.v1"
MIGRATION_VERIFICATION_SCHEMA_V1 = "lukart.lrd-cross-algorithm-verification.v1"

ML_DSA_FAMILY = "ML-DSA"
ML_DSA_PARAMETER_SET = "ML-DSA-65"
ML_DSA_STANDARD = "NIST-FIPS-204"
ML_DSA_STANDARD_REVISION = "FIPS-204-final-2024-08-13"
ML_DSA_ERRATA_REFERENCE = "NIST-CSRC-planning-note-2026-07-31"
CRYPTOGRAPHY_IMPLEMENTATION = "pyca-cryptography"
CRYPTOGRAPHY_VERSION = "50.0.1"
UV_LOCK_BLOB_SHA = "9c018011129dc660a1451289de3befb1f92d7280"
NIST_ACVP_REPOSITORY = "usnistgov/ACVP-Server"
NIST_ACVP_COMMIT_SHA = "975de31eb83d87039ec88934fdc47d8c312b892d"
NIST_ACVP_PROMPT_BLOB_SHA = "f53809df5fefee2c1b80da1122885a2e0e843e32"
NIST_ACVP_EXPECTED_BLOB_SHA = "38213cd71c20c019cc49bf140f616ed86c81ad98"
NIST_ACVP_VECTOR_GROUP_ID = 2
NIST_ACVP_VECTOR_CASE_ID = 26
ML_DSA_PUBLIC_KEY_BYTES = 1952
ML_DSA_SIGNATURE_BYTES = 3309
ML_DSA_CONTEXT = b"LUKART-LRD-01J-ML-DSA-65-v1"
SIGN_BUDGET_MS = 1000.0
VERIFY_BUDGET_MS = 1000.0


class CrossAlgorithmMigrationError(ValueError):
    """Fail-closed LRD-01J contract violation."""


class MigrationEvidenceState(StrEnum):
    DUAL_VERIFIED_ADDITIVE_EVIDENCE = "DUAL_VERIFIED_ADDITIVE_EVIDENCE"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CrossAlgorithmMigrationError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CrossAlgorithmMigrationError(f"{field_name} must be a nonnegative integer")
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(_text(value, field_name=field_name), field_name=field_name)
    except ValueError as exc:
        raise CrossAlgorithmMigrationError(str(exc)) from exc


def _strict_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise CrossAlgorithmMigrationError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _decode_b64(value: str, *, field_name: str, expected_size: int) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CrossAlgorithmMigrationError(f"{field_name} must be canonical base64") from exc
    if len(raw) != expected_size:
        raise CrossAlgorithmMigrationError(
            f"{field_name} must be exactly {expected_size} bytes"
        )
    if base64.b64encode(raw).decode("ascii") != value:
        raise CrossAlgorithmMigrationError(f"{field_name} base64 is not canonical")
    return raw


@dataclass(frozen=True, slots=True)
class Mldsa65AdapterProfileV1:
    family: str = ML_DSA_FAMILY
    parameter_set: str = ML_DSA_PARAMETER_SET
    standard_id: str = ML_DSA_STANDARD
    standard_revision: str = ML_DSA_STANDARD_REVISION
    errata_reference: str = ML_DSA_ERRATA_REFERENCE
    errata_incorporated_claim: bool = False
    implementation: str = CRYPTOGRAPHY_IMPLEMENTATION
    implementation_version: str = CRYPTOGRAPHY_VERSION
    dependency_lock_blob_sha: str = UV_LOCK_BLOB_SHA
    public_key_bytes: int = ML_DSA_PUBLIC_KEY_BYTES
    signature_bytes: int = ML_DSA_SIGNATURE_BYTES
    context: str = ML_DSA_CONTEXT.decode("ascii")
    nist_acvp_repository: str = NIST_ACVP_REPOSITORY
    nist_acvp_commit_sha: str = NIST_ACVP_COMMIT_SHA
    nist_acvp_prompt_blob_sha: str = NIST_ACVP_PROMPT_BLOB_SHA
    nist_acvp_expected_blob_sha: str = NIST_ACVP_EXPECTED_BLOB_SHA
    nist_acvp_vector_group_id: int = NIST_ACVP_VECTOR_GROUP_ID
    nist_acvp_vector_case_id: int = NIST_ACVP_VECTOR_CASE_ID
    cross_implementation_interoperability_proven: bool = False
    fips_validation_claim: bool = False
    schema: str = ADAPTER_PROFILE_SCHEMA_V1

    def __post_init__(self) -> None:
        expected = Mldsa65AdapterProfileV1.__new__(Mldsa65AdapterProfileV1)
        fixed: dict[str, object] = {
            "schema": ADAPTER_PROFILE_SCHEMA_V1,
            "family": ML_DSA_FAMILY,
            "parameter_set": ML_DSA_PARAMETER_SET,
            "standard_id": ML_DSA_STANDARD,
            "standard_revision": ML_DSA_STANDARD_REVISION,
            "errata_reference": ML_DSA_ERRATA_REFERENCE,
            "errata_incorporated_claim": False,
            "implementation": CRYPTOGRAPHY_IMPLEMENTATION,
            "implementation_version": CRYPTOGRAPHY_VERSION,
            "dependency_lock_blob_sha": UV_LOCK_BLOB_SHA,
            "public_key_bytes": ML_DSA_PUBLIC_KEY_BYTES,
            "signature_bytes": ML_DSA_SIGNATURE_BYTES,
            "context": ML_DSA_CONTEXT.decode("ascii"),
            "nist_acvp_repository": NIST_ACVP_REPOSITORY,
            "nist_acvp_commit_sha": NIST_ACVP_COMMIT_SHA,
            "nist_acvp_prompt_blob_sha": NIST_ACVP_PROMPT_BLOB_SHA,
            "nist_acvp_expected_blob_sha": NIST_ACVP_EXPECTED_BLOB_SHA,
            "nist_acvp_vector_group_id": NIST_ACVP_VECTOR_GROUP_ID,
            "nist_acvp_vector_case_id": NIST_ACVP_VECTOR_CASE_ID,
            "cross_implementation_interoperability_proven": False,
            "fips_validation_claim": False,
        }
        del expected
        for name, value in fixed.items():
            if getattr(self, name) != value:
                raise CrossAlgorithmMigrationError(
                    f"ML-DSA-65 adapter profile field {name} is fixed in v1"
                )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "family": self.family,
            "parameter_set": self.parameter_set,
            "standard_id": self.standard_id,
            "standard_revision": self.standard_revision,
            "errata_reference": self.errata_reference,
            "errata_incorporated_claim": self.errata_incorporated_claim,
            "implementation": self.implementation,
            "implementation_version": self.implementation_version,
            "dependency_lock_blob_sha": self.dependency_lock_blob_sha,
            "public_key_bytes": self.public_key_bytes,
            "signature_bytes": self.signature_bytes,
            "context": self.context,
            "nist_acvp_repository": self.nist_acvp_repository,
            "nist_acvp_commit_sha": self.nist_acvp_commit_sha,
            "nist_acvp_prompt_blob_sha": self.nist_acvp_prompt_blob_sha,
            "nist_acvp_expected_blob_sha": self.nist_acvp_expected_blob_sha,
            "nist_acvp_vector_group_id": self.nist_acvp_vector_group_id,
            "nist_acvp_vector_case_id": self.nist_acvp_vector_case_id,
            "cross_implementation_interoperability_proven": (
                self.cross_implementation_interoperability_proven
            ),
            "fips_validation_claim": self.fips_validation_claim,
        }

    @property
    def profile_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class Mldsa65RuntimeProvenanceV1:
    cryptography_version: str
    openssl_version: str
    python_implementation: str
    python_version: str
    platform_system: str
    platform_machine: str
    schema: str = RUNTIME_PROVENANCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RUNTIME_PROVENANCE_SCHEMA_V1:
            raise CrossAlgorithmMigrationError("unsupported runtime provenance schema")
        for name in (
            "cryptography_version",
            "openssl_version",
            "python_implementation",
            "python_version",
            "platform_system",
            "platform_machine",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))

    @classmethod
    def current(cls) -> Mldsa65RuntimeProvenanceV1:
        if cryptography.__version__ != CRYPTOGRAPHY_VERSION:
            raise CrossAlgorithmMigrationError(
                "runtime cryptography version does not match pinned adapter profile"
            )
        return cls(
            cryptography_version=cryptography.__version__,
            openssl_version=openssl_backend.openssl_version_text(),
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            platform_system=platform.system(),
            platform_machine=platform.machine() or "unknown-machine",
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cryptography_version": self.cryptography_version,
            "openssl_version": self.openssl_version,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
        }

    @property
    def provenance_digest(self) -> str:
        return content_digest(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Mldsa65RuntimeProvenanceV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "cryptography_version",
                    "openssl_version",
                    "python_implementation",
                    "python_version",
                    "platform_system",
                    "platform_machine",
                }
            ),
            field_name="runtime provenance",
        )
        return cls(
            schema=_text(value.get("schema"), field_name="schema"),
            cryptography_version=_text(
                value.get("cryptography_version"), field_name="cryptography_version"
            ),
            openssl_version=_text(value.get("openssl_version"), field_name="openssl_version"),
            python_implementation=_text(
                value.get("python_implementation"), field_name="python_implementation"
            ),
            python_version=_text(value.get("python_version"), field_name="python_version"),
            platform_system=_text(value.get("platform_system"), field_name="platform_system"),
            platform_machine=_text(
                value.get("platform_machine"), field_name="platform_machine"
            ),
        )


@dataclass(frozen=True, slots=True)
class Mldsa65MigrationKeyV1:
    key_id: str
    public_key_b64: str
    status: CryptoKeyStatus
    not_before: int
    allowed_purposes: tuple[AttestationPurpose, ...]
    predecessor_ed25519_key_id: str
    adapter_profile_digest: str
    retire_at: int | None = None
    schema: str = MIGRATION_KEY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != MIGRATION_KEY_SCHEMA_V1:
            raise CrossAlgorithmMigrationError("unsupported migration key schema")
        object.__setattr__(self, "key_id", _text(self.key_id, field_name="key_id"))
        object.__setattr__(
            self,
            "predecessor_ed25519_key_id",
            _text(self.predecessor_ed25519_key_id, field_name="predecessor_ed25519_key_id"),
        )
        object.__setattr__(
            self,
            "adapter_profile_digest",
            _digest(self.adapter_profile_digest, field_name="adapter_profile_digest"),
        )
        _decode_b64(
            _text(self.public_key_b64, field_name="public_key_b64"),
            field_name="ML-DSA-65 public key",
            expected_size=ML_DSA_PUBLIC_KEY_BYTES,
        )
        object.__setattr__(self, "not_before", _int(self.not_before, field_name="not_before"))
        if not isinstance(self.status, CryptoKeyStatus):
            raise CrossAlgorithmMigrationError("unknown migration key lifecycle status")
        retire_at = self.retire_at
        if retire_at is not None:
            retire_at = _int(retire_at, field_name="retire_at")
            if retire_at <= self.not_before:
                raise CrossAlgorithmMigrationError("retire_at must be after not_before")
        if self.status is CryptoKeyStatus.RETIRED and retire_at is None:
            raise CrossAlgorithmMigrationError("RETIRED migration key requires retire_at")
        if not self.allowed_purposes:
            raise CrossAlgorithmMigrationError("allowed_purposes cannot be empty")
        if any(not isinstance(item, AttestationPurpose) for item in self.allowed_purposes):
            raise CrossAlgorithmMigrationError("allowed_purposes contains unknown purpose")
        purposes = tuple(sorted(set(self.allowed_purposes), key=lambda item: item.value))
        object.__setattr__(self, "retire_at", retire_at)
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
        predecessor_ed25519_key_id: str,
        adapter_profile_digest: str,
        retire_at: int | None = None,
    ) -> Mldsa65MigrationKeyV1:
        return cls(
            key_id=key_id,
            public_key_b64=base64.b64encode(public_key).decode("ascii"),
            status=status,
            not_before=not_before,
            allowed_purposes=tuple(allowed_purposes),
            predecessor_ed25519_key_id=predecessor_ed25519_key_id,
            adapter_profile_digest=adapter_profile_digest,
            retire_at=retire_at,
        )

    def public_key_bytes(self) -> bytes:
        return _decode_b64(
            self.public_key_b64,
            field_name="ML-DSA-65 public key",
            expected_size=ML_DSA_PUBLIC_KEY_BYTES,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "key_id": self.key_id,
            "public_key_b64": self.public_key_b64,
            "status": self.status.value,
            "not_before": self.not_before,
            "retire_at": self.retire_at,
            "allowed_purposes": [item.value for item in self.allowed_purposes],
            "predecessor_ed25519_key_id": self.predecessor_ed25519_key_id,
            "adapter_profile_digest": self.adapter_profile_digest,
        }

    @property
    def key_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CrossAlgorithmMigrationEnvelopeV1:
    source_attestation_digest: str
    source_verification_digest: str
    source_trust_set_digest: str
    source_key_digest: str
    purpose: AttestationPurpose
    subject_digest: str
    payload_digest: str
    migration_key_digest: str
    adapter_profile_digest: str
    signer_runtime: Mldsa65RuntimeProvenanceV1
    issued_at: int
    nonce: str
    signature_b64: str
    schema: str = MIGRATION_ENVELOPE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != MIGRATION_ENVELOPE_SCHEMA_V1:
            raise CrossAlgorithmMigrationError("unsupported migration envelope schema")
        for name in (
            "source_attestation_digest",
            "source_verification_digest",
            "source_trust_set_digest",
            "source_key_digest",
            "subject_digest",
            "payload_digest",
            "migration_key_digest",
            "adapter_profile_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        if not isinstance(self.purpose, AttestationPurpose):
            raise CrossAlgorithmMigrationError("unknown migration purpose")
        if not isinstance(self.signer_runtime, Mldsa65RuntimeProvenanceV1):
            raise CrossAlgorithmMigrationError("invalid signer runtime provenance")
        object.__setattr__(self, "issued_at", _int(self.issued_at, field_name="issued_at"))
        object.__setattr__(self, "nonce", _text(self.nonce, field_name="nonce"))
        _decode_b64(
            _text(self.signature_b64, field_name="signature_b64"),
            field_name="ML-DSA-65 signature",
            expected_size=ML_DSA_SIGNATURE_BYTES,
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_attestation_digest": self.source_attestation_digest,
            "source_verification_digest": self.source_verification_digest,
            "source_trust_set_digest": self.source_trust_set_digest,
            "source_key_digest": self.source_key_digest,
            "purpose": self.purpose.value,
            "subject_digest": self.subject_digest,
            "payload_digest": self.payload_digest,
            "migration_key_digest": self.migration_key_digest,
            "adapter_profile_digest": self.adapter_profile_digest,
            "signer_runtime": self.signer_runtime.canonical_dict(),
            "issued_at": self.issued_at,
            "nonce": self.nonce,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "signature_b64": self.signature_b64}

    @property
    def envelope_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CrossAlgorithmVerificationV1:
    source_verification_digest: str
    migration_envelope_digest: str
    migration_key_digest: str
    adapter_profile_digest: str
    signer_runtime_digest: str
    state: MigrationEvidenceState = MigrationEvidenceState.DUAL_VERIFIED_ADDITIVE_EVIDENCE
    automation_can_promote_trust: bool = False
    fips_validation_claim: bool = False
    independent_crypto_review_claim: bool = False
    schema: str = MIGRATION_VERIFICATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != MIGRATION_VERIFICATION_SCHEMA_V1:
            raise CrossAlgorithmMigrationError("unsupported migration verification schema")
        for name in (
            "source_verification_digest",
            "migration_envelope_digest",
            "migration_key_digest",
            "adapter_profile_digest",
            "signer_runtime_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        if self.state is not MigrationEvidenceState.DUAL_VERIFIED_ADDITIVE_EVIDENCE:
            raise CrossAlgorithmMigrationError("unknown migration verification state")
        if (
            self.automation_can_promote_trust
            or self.fips_validation_claim
            or self.independent_crypto_review_claim
        ):
            raise CrossAlgorithmMigrationError("01J cannot manufacture trust/certification claims")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_verification_digest": self.source_verification_digest,
            "migration_envelope_digest": self.migration_envelope_digest,
            "migration_key_digest": self.migration_key_digest,
            "adapter_profile_digest": self.adapter_profile_digest,
            "signer_runtime_digest": self.signer_runtime_digest,
            "state": self.state.value,
            "automation_can_promote_trust": self.automation_can_promote_trust,
            "fips_validation_claim": self.fips_validation_claim,
            "independent_crypto_review_claim": self.independent_crypto_review_claim,
        }

    @property
    def verification_digest(self) -> str:
        return content_digest(self.canonical_dict())


def require_mldsa65_runtime_support_v1() -> Mldsa65RuntimeProvenanceV1:
    """Fail closed unless the exact pinned runtime exposes a working ML-DSA-65 backend."""

    runtime = Mldsa65RuntimeProvenanceV1.current()
    try:
        private_key = MLDSA65PrivateKey.generate()
        public_key = private_key.public_key()
        probe = b"LRD-01J-runtime-capability-probe"
        signature = private_key.sign(probe, ML_DSA_CONTEXT)
        public_key.verify(signature, probe, ML_DSA_CONTEXT)
    except (UnsupportedAlgorithm, InvalidSignature, ValueError) as exc:
        raise CrossAlgorithmMigrationError("ML-DSA-65 runtime capability unavailable") from exc
    if len(public_key.public_bytes_raw()) != ML_DSA_PUBLIC_KEY_BYTES:
        raise CrossAlgorithmMigrationError("ML-DSA-65 public-key size contract mismatch")
    if len(signature) != ML_DSA_SIGNATURE_BYTES:
        raise CrossAlgorithmMigrationError("ML-DSA-65 signature size contract mismatch")
    return runtime


def _verify_source(
    *,
    source_attestation: SignedAttestation,
    source_payload: Mapping[str, object],
    source_trust_set: CryptoTrustSetV1,
    expected_source_trust_set_digest: str,
    expected_purpose: AttestationPurpose,
    expected_subject_digest: str,
    now: int,
):
    return CryptoTrustVerifierV1(
        source_trust_set,
        expected_trust_set_digest=expected_source_trust_set_digest,
    ).verify(
        source_attestation,
        expected_purpose=expected_purpose,
        expected_subject_digest=expected_subject_digest,
        payload=source_payload,
        now=now,
    )


def sign_cross_algorithm_migration_v1(
    *,
    source_attestation: SignedAttestation,
    source_payload: Mapping[str, object],
    source_trust_set: CryptoTrustSetV1,
    expected_source_trust_set_digest: str,
    migration_key: Mldsa65MigrationKeyV1,
    expected_migration_key_digest: str,
    adapter_profile: Mldsa65AdapterProfileV1,
    expected_adapter_profile_digest: str,
    private_key: MLDSA65PrivateKey,
    issued_at: int,
    nonce: str,
) -> CrossAlgorithmMigrationEnvelopeV1:
    """Verify the historical CRY-01 proof first, then add an ML-DSA-65 proof."""

    issued_at = _int(issued_at, field_name="issued_at")
    expected_source = _digest(
        expected_source_trust_set_digest,
        field_name="expected_source_trust_set_digest",
    )
    expected_key = _digest(expected_migration_key_digest, field_name="expected_migration_key_digest")
    expected_profile = _digest(
        expected_adapter_profile_digest,
        field_name="expected_adapter_profile_digest",
    )
    if source_trust_set.trust_set_digest != expected_source:
        raise CrossAlgorithmMigrationError("source trust-set identity mismatch")
    if migration_key.key_digest != expected_key:
        raise CrossAlgorithmMigrationError("migration key identity mismatch")
    if adapter_profile.profile_digest != expected_profile:
        raise CrossAlgorithmMigrationError("adapter profile identity mismatch")
    if migration_key.adapter_profile_digest != adapter_profile.profile_digest:
        raise CrossAlgorithmMigrationError("migration key is bound to another adapter profile")
    if migration_key.status is not CryptoKeyStatus.ACTIVE:
        raise CrossAlgorithmMigrationError("only ACTIVE migration key may sign")
    if source_attestation.purpose not in migration_key.allowed_purposes:
        raise CrossAlgorithmMigrationError("source purpose is not allowed for migration key")
    if migration_key.predecessor_ed25519_key_id != source_attestation.key_id:
        raise CrossAlgorithmMigrationError("migration predecessor does not match source key")
    if issued_at < migration_key.not_before:
        raise CrossAlgorithmMigrationError("cannot sign before migration key activation")
    if migration_key.retire_at is not None and issued_at >= migration_key.retire_at:
        raise CrossAlgorithmMigrationError("cannot sign at or after migration key retirement")
    if issued_at < source_attestation.issued_at:
        raise CrossAlgorithmMigrationError("migration cannot predate source attestation")

    runtime = require_mldsa65_runtime_support_v1()
    if private_key.public_key().public_bytes_raw() != migration_key.public_key_bytes():
        raise CrossAlgorithmMigrationError("private key does not match pinned migration key")

    source_verification = _verify_source(
        source_attestation=source_attestation,
        source_payload=source_payload,
        source_trust_set=source_trust_set,
        expected_source_trust_set_digest=expected_source,
        expected_purpose=source_attestation.purpose,
        expected_subject_digest=source_attestation.subject_digest,
        now=issued_at,
    )
    payload_digest = content_digest(dict(source_payload))
    body: dict[str, object] = {
        "schema": MIGRATION_ENVELOPE_SCHEMA_V1,
        "source_attestation_digest": source_attestation.digest(),
        "source_verification_digest": source_verification.verification_digest,
        "source_trust_set_digest": source_verification.trust_set_digest,
        "source_key_digest": source_verification.key_digest,
        "purpose": source_attestation.purpose.value,
        "subject_digest": source_attestation.subject_digest,
        "payload_digest": payload_digest,
        "migration_key_digest": migration_key.key_digest,
        "adapter_profile_digest": adapter_profile.profile_digest,
        "signer_runtime": runtime.canonical_dict(),
        "issued_at": issued_at,
        "nonce": _text(nonce, field_name="nonce"),
    }
    try:
        signature = private_key.sign(canonical_json(body).encode("utf-8"), ML_DSA_CONTEXT)
    except (UnsupportedAlgorithm, ValueError) as exc:
        raise CrossAlgorithmMigrationError("ML-DSA-65 signing failed") from exc
    return CrossAlgorithmMigrationEnvelopeV1(
        source_attestation_digest=source_attestation.digest(),
        source_verification_digest=source_verification.verification_digest,
        source_trust_set_digest=source_verification.trust_set_digest,
        source_key_digest=source_verification.key_digest,
        purpose=source_attestation.purpose,
        subject_digest=source_attestation.subject_digest,
        payload_digest=payload_digest,
        migration_key_digest=migration_key.key_digest,
        adapter_profile_digest=adapter_profile.profile_digest,
        signer_runtime=runtime,
        issued_at=issued_at,
        nonce=_text(nonce, field_name="nonce"),
        signature_b64=base64.b64encode(signature).decode("ascii"),
    )


def verify_cross_algorithm_migration_v1(
    *,
    envelope: CrossAlgorithmMigrationEnvelopeV1,
    source_attestation: SignedAttestation,
    source_payload: Mapping[str, object],
    source_trust_set: CryptoTrustSetV1,
    expected_source_trust_set_digest: str,
    migration_key: Mldsa65MigrationKeyV1,
    expected_migration_key_digest: str,
    adapter_profile: Mldsa65AdapterProfileV1,
    expected_adapter_profile_digest: str,
    now: int,
) -> CrossAlgorithmVerificationV1:
    """Require both the historical Ed25519 proof and the additive ML-DSA-65 proof."""

    now = _int(now, field_name="now")
    expected_source = _digest(
        expected_source_trust_set_digest,
        field_name="expected_source_trust_set_digest",
    )
    expected_key = _digest(expected_migration_key_digest, field_name="expected_migration_key_digest")
    expected_profile = _digest(
        expected_adapter_profile_digest,
        field_name="expected_adapter_profile_digest",
    )
    if source_trust_set.trust_set_digest != expected_source:
        raise CrossAlgorithmMigrationError("source trust-set identity mismatch")
    if migration_key.key_digest != expected_key:
        raise CrossAlgorithmMigrationError("migration key identity mismatch")
    if adapter_profile.profile_digest != expected_profile:
        raise CrossAlgorithmMigrationError("adapter profile identity mismatch")
    if migration_key.adapter_profile_digest != adapter_profile.profile_digest:
        raise CrossAlgorithmMigrationError("migration key is bound to another adapter profile")
    if migration_key.status is CryptoKeyStatus.REVOKED:
        raise CrossAlgorithmMigrationError("migration key is revoked")
    if envelope.purpose not in migration_key.allowed_purposes:
        raise CrossAlgorithmMigrationError("envelope purpose is not allowed for migration key")
    if migration_key.predecessor_ed25519_key_id != source_attestation.key_id:
        raise CrossAlgorithmMigrationError("migration predecessor does not match source key")
    if envelope.issued_at < migration_key.not_before:
        raise CrossAlgorithmMigrationError("envelope predates migration key activation")
    if migration_key.retire_at is not None and envelope.issued_at >= migration_key.retire_at:
        raise CrossAlgorithmMigrationError("envelope was issued after migration key retirement")
    if now < envelope.issued_at:
        raise CrossAlgorithmMigrationError("migration envelope is not yet valid")

    require_mldsa65_runtime_support_v1()
    source_verification = _verify_source(
        source_attestation=source_attestation,
        source_payload=source_payload,
        source_trust_set=source_trust_set,
        expected_source_trust_set_digest=expected_source,
        expected_purpose=envelope.purpose,
        expected_subject_digest=envelope.subject_digest,
        now=now,
    )
    expected_bindings: dict[str, object] = {
        "source_attestation_digest": source_attestation.digest(),
        "source_verification_digest": source_verification.verification_digest,
        "source_trust_set_digest": source_verification.trust_set_digest,
        "source_key_digest": source_verification.key_digest,
        "purpose": source_attestation.purpose,
        "subject_digest": source_attestation.subject_digest,
        "payload_digest": content_digest(dict(source_payload)),
        "migration_key_digest": migration_key.key_digest,
        "adapter_profile_digest": adapter_profile.profile_digest,
    }
    for name, expected in expected_bindings.items():
        if getattr(envelope, name) != expected:
            raise CrossAlgorithmMigrationError(f"migration envelope {name} mismatch")

    signature = _decode_b64(
        envelope.signature_b64,
        field_name="ML-DSA-65 signature",
        expected_size=ML_DSA_SIGNATURE_BYTES,
    )
    try:
        public_key = MLDSA65PublicKey.from_public_bytes(migration_key.public_key_bytes())
        public_key.verify(
            signature,
            canonical_json(envelope.canonical_body()).encode("utf-8"),
            ML_DSA_CONTEXT,
        )
    except (UnsupportedAlgorithm, InvalidSignature, ValueError) as exc:
        raise CrossAlgorithmMigrationError("ML-DSA-65 migration signature invalid") from exc

    return CrossAlgorithmVerificationV1(
        source_verification_digest=source_verification.verification_digest,
        migration_envelope_digest=envelope.envelope_digest,
        migration_key_digest=migration_key.key_digest,
        adapter_profile_digest=adapter_profile.profile_digest,
        signer_runtime_digest=envelope.signer_runtime.provenance_digest,
    )


def measure_mldsa65_performance_v1(*, iterations: int = 5) -> dict[str, object]:
    """Bounded runtime measurement; timing is operational evidence, not semantic identity."""

    if not isinstance(iterations, int) or isinstance(iterations, bool) or not 1 <= iterations <= 50:
        raise CrossAlgorithmMigrationError("iterations must be in range 1..50")
    require_mldsa65_runtime_support_v1()
    private_key = MLDSA65PrivateKey.generate()
    public_key = private_key.public_key()
    message = b"LRD-01J-bounded-performance-probe"
    sign_ms: list[float] = []
    verify_ms: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        signature = private_key.sign(message, ML_DSA_CONTEXT)
        sign_ms.append((time.perf_counter() - start) * 1000.0)
        start = time.perf_counter()
        public_key.verify(signature, message, ML_DSA_CONTEXT)
        verify_ms.append((time.perf_counter() - start) * 1000.0)
    max_sign = max(sign_ms)
    max_verify = max(verify_ms)
    return {
        "parameter_set": ML_DSA_PARAMETER_SET,
        "iterations": iterations,
        "max_sign_ms": max_sign,
        "max_verify_ms": max_verify,
        "sign_budget_ms": SIGN_BUDGET_MS,
        "verify_budget_ms": VERIFY_BUDGET_MS,
        "within_budget": max_sign <= SIGN_BUDGET_MS and max_verify <= VERIFY_BUDGET_MS,
    }
