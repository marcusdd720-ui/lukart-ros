"""LRD-01E crypto renewal, storage portability and freshness-aware health evidence.

This module composes CRY-01, DR-02 and LRD-01C. It is verification-only: it does not
store private keys, mutate the Canonical Case Ledger, promote trust, or publish releases.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowBackendV1,
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
    migrate_verified_blob,
)
from core.crypto_agility_v1 import (
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import AttestationPurpose, AttestationSigner, SignedAttestation
from core.enterprise.recovery_continuity_v1 import (
    RecoveryConformanceReportV1,
    RecoveryConformanceState,
    RecoveryDrillManifestV1,
    StorageProfileV1,
)
from core.long_range_replay_v1 import LongRangeReplayManifestV1
from core.p3.contracts import content_digest, require_hex_digest

CRYPTO_RENEWAL_SCHEMA_V1 = "lukart.lrd-crypto-renewal.v1"
PORTABILITY_DRILL_SCHEMA_V1 = "lukart.lrd-storage-portability-drill.v1"
FRESHNESS_POLICY_SCHEMA_V1 = "lukart.lrd-freshness-policy.v1"
LONG_RANGE_HEALTH_SCHEMA_V1 = "lukart.lrd-health-report.v1"


class LongRangeHealthError(ValueError):
    """Fail-closed LRD-01E contract violation."""


class HealthDimensionState(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    FAIL = "FAIL"


class LongRangeHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"
    DEGRADED = "DEGRADED"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise LongRangeHealthError(f"{field_name} must be nonblank and canonical")
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(_text(value, field_name=field_name), field_name=field_name)
    except ValueError as exc:
        raise LongRangeHealthError(str(exc)) from exc


def _int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LongRangeHealthError(f"{field_name} must be a nonnegative integer")
    return value


def _strict_keys(value: Mapping[str, object], expected: frozenset[str], *, field_name: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise LongRangeHealthError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _signed_attestation_dict(value: SignedAttestation) -> dict[str, object]:
    return {**value.canonical_body(), "signature_b64": value.signature_b64}


def _signed_attestation_from_dict(value: Mapping[str, object]) -> SignedAttestation:
    expected = frozenset(
        {
            "key_id",
            "purpose",
            "subject_digest",
            "payload_digest",
            "issued_at",
            "expires_at",
            "nonce",
            "signature_b64",
        }
    )
    _strict_keys(value, expected, field_name="signed attestation")
    expires_raw = value.get("expires_at")
    expires_at = None if expires_raw is None else _int(expires_raw, field_name="expires_at")
    try:
        purpose = AttestationPurpose(_text(value.get("purpose"), field_name="purpose"))
    except ValueError as exc:
        raise LongRangeHealthError("unknown attestation purpose") from exc
    return SignedAttestation(
        key_id=_text(value.get("key_id"), field_name="key_id"),
        purpose=purpose,
        subject_digest=_digest(value.get("subject_digest"), field_name="subject_digest"),
        payload_digest=_digest(value.get("payload_digest"), field_name="payload_digest"),
        issued_at=_int(value.get("issued_at"), field_name="issued_at"),
        expires_at=expires_at,
        nonce=_text(value.get("nonce"), field_name="nonce"),
        signature_b64=_text(value.get("signature_b64"), field_name="signature_b64"),
    )


@dataclass(frozen=True, slots=True)
class FreshnessPolicyV1:
    crypto_renewal_max_age_seconds: int
    portability_max_age_seconds: int
    recovery_max_age_seconds: int
    schema: str = FRESHNESS_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != FRESHNESS_POLICY_SCHEMA_V1:
            raise LongRangeHealthError(f"unsupported freshness policy schema: {self.schema}")
        for name in (
            "crypto_renewal_max_age_seconds",
            "portability_max_age_seconds",
            "recovery_max_age_seconds",
        ):
            value = _int(getattr(self, name), field_name=name)
            if value == 0:
                raise LongRangeHealthError(f"{name} must be positive")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "crypto_renewal_max_age_seconds": self.crypto_renewal_max_age_seconds,
            "portability_max_age_seconds": self.portability_max_age_seconds,
            "recovery_max_age_seconds": self.recovery_max_age_seconds,
        }

    @property
    def policy_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CryptoRenewalAttestationV1:
    case_id: str
    subject_digest: str
    purpose: AttestationPurpose
    historical_attestation_digest: str
    historical_trust_set_digest: str
    historical_verification_digest: str
    renewed_attestation: SignedAttestation
    current_trust_set_digest: str
    current_verification_digest: str
    renewed_at: int
    schema: str = CRYPTO_RENEWAL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRYPTO_RENEWAL_SCHEMA_V1:
            raise LongRangeHealthError(f"unsupported crypto renewal schema: {self.schema}")
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "subject_digest",
            "historical_attestation_digest",
            "historical_trust_set_digest",
            "historical_verification_digest",
            "current_trust_set_digest",
            "current_verification_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        object.__setattr__(self, "renewed_at", _int(self.renewed_at, field_name="renewed_at"))
        if not isinstance(self.purpose, AttestationPurpose):
            raise LongRangeHealthError("unknown renewal purpose")
        if self.renewed_attestation.subject_digest != self.subject_digest:
            raise LongRangeHealthError("renewed attestation subject mismatch")
        if self.renewed_attestation.purpose is not self.purpose:
            raise LongRangeHealthError("renewed attestation purpose mismatch")
        if self.renewed_attestation.issued_at != self.renewed_at:
            raise LongRangeHealthError("renewed attestation timestamp mismatch")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "subject_digest": self.subject_digest,
            "purpose": self.purpose.value,
            "historical_attestation_digest": self.historical_attestation_digest,
            "historical_trust_set_digest": self.historical_trust_set_digest,
            "historical_verification_digest": self.historical_verification_digest,
            "renewed_attestation": _signed_attestation_dict(self.renewed_attestation),
            "current_trust_set_digest": self.current_trust_set_digest,
            "current_verification_digest": self.current_verification_digest,
            "renewed_at": self.renewed_at,
        }

    @property
    def renewal_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "renewal_digest": self.renewal_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CryptoRenewalAttestationV1:
        expected = frozenset(
            {
                "schema",
                "case_id",
                "subject_digest",
                "purpose",
                "historical_attestation_digest",
                "historical_trust_set_digest",
                "historical_verification_digest",
                "renewed_attestation",
                "current_trust_set_digest",
                "current_verification_digest",
                "renewed_at",
                "renewal_digest",
            }
        )
        _strict_keys(value, expected, field_name="crypto renewal")
        raw_attestation = value.get("renewed_attestation")
        if not isinstance(raw_attestation, Mapping):
            raise LongRangeHealthError("renewed_attestation must be an object")
        try:
            purpose = AttestationPurpose(_text(value.get("purpose"), field_name="purpose"))
        except ValueError as exc:
            raise LongRangeHealthError("unknown renewal purpose") from exc
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            subject_digest=_digest(value.get("subject_digest"), field_name="subject_digest"),
            purpose=purpose,
            historical_attestation_digest=_digest(
                value.get("historical_attestation_digest"), field_name="historical_attestation_digest"
            ),
            historical_trust_set_digest=_digest(
                value.get("historical_trust_set_digest"), field_name="historical_trust_set_digest"
            ),
            historical_verification_digest=_digest(
                value.get("historical_verification_digest"), field_name="historical_verification_digest"
            ),
            renewed_attestation=_signed_attestation_from_dict(
                cast(Mapping[str, object], raw_attestation)
            ),
            current_trust_set_digest=_digest(
                value.get("current_trust_set_digest"), field_name="current_trust_set_digest"
            ),
            current_verification_digest=_digest(
                value.get("current_verification_digest"), field_name="current_verification_digest"
            ),
            renewed_at=_int(value.get("renewed_at"), field_name="renewed_at"),
        )
        if _digest(value.get("renewal_digest"), field_name="renewal_digest") != result.renewal_digest:
            raise LongRangeHealthError("crypto renewal digest mismatch")
        return result


def renew_crypto_attestation_v1(
    *,
    case_id: str,
    historical_attestation: SignedAttestation,
    historical_payload: Mapping[str, object],
    historical_trust_set: CryptoTrustSetV1,
    current_trust_set: CryptoTrustSetV1,
    current_signer: AttestationSigner,
    renewed_at: int,
    expires_at: int | None,
    nonce: str,
) -> CryptoRenewalAttestationV1:
    """Verify historical proof, then add a new chained proof over the same immutable subject."""

    renewed_at = _int(renewed_at, field_name="renewed_at")
    historical_verification = CryptoTrustVerifierV1(
        historical_trust_set,
        expected_trust_set_digest=historical_trust_set.trust_set_digest,
    ).verify(
        historical_attestation,
        expected_purpose=historical_attestation.purpose,
        expected_subject_digest=historical_attestation.subject_digest,
        payload=historical_payload,
        now=renewed_at,
    )
    if current_trust_set.previous_trust_set_digest != historical_trust_set.trust_set_digest:
        raise LongRangeHealthError("current trust set is not chained to historical trust set")
    renewal_payload: dict[str, object] = {
        "schema": CRYPTO_RENEWAL_SCHEMA_V1,
        "case_id": _text(case_id, field_name="case_id"),
        "historical_attestation_digest": historical_attestation.digest(),
        "historical_trust_set_digest": historical_trust_set.trust_set_digest,
    }
    renewed = sign_attestation_v1(
        trust_set=current_trust_set,
        expected_trust_set_digest=current_trust_set.trust_set_digest,
        signer=current_signer,
        purpose=historical_attestation.purpose,
        subject_digest=historical_attestation.subject_digest,
        payload=renewal_payload,
        issued_at=renewed_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    current_verification = CryptoTrustVerifierV1(
        current_trust_set,
        expected_trust_set_digest=current_trust_set.trust_set_digest,
    ).verify(
        renewed,
        expected_purpose=historical_attestation.purpose,
        expected_subject_digest=historical_attestation.subject_digest,
        payload=renewal_payload,
        now=renewed_at,
    )
    return CryptoRenewalAttestationV1(
        case_id=cast(str, renewal_payload["case_id"]),
        subject_digest=historical_attestation.subject_digest,
        purpose=historical_attestation.purpose,
        historical_attestation_digest=historical_attestation.digest(),
        historical_trust_set_digest=historical_trust_set.trust_set_digest,
        historical_verification_digest=historical_verification.verification_digest,
        renewed_attestation=renewed,
        current_trust_set_digest=current_trust_set.trust_set_digest,
        current_verification_digest=current_verification.verification_digest,
        renewed_at=renewed_at,
    )


@dataclass(frozen=True, slots=True)
class StoragePortabilityDrillV1:
    case_id: str
    escrow_manifest_digest: str
    source_profile_digest: str
    target_profile_digest: str
    artifact_count: int
    total_bytes: int
    migrated_blob_set_digest: str
    observed_at: int
    schema: str = PORTABILITY_DRILL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PORTABILITY_DRILL_SCHEMA_V1:
            raise LongRangeHealthError(f"unsupported portability schema: {self.schema}")
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "escrow_manifest_digest",
            "source_profile_digest",
            "target_profile_digest",
            "migrated_blob_set_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        object.__setattr__(self, "artifact_count", _int(self.artifact_count, field_name="artifact_count"))
        object.__setattr__(self, "total_bytes", _int(self.total_bytes, field_name="total_bytes"))
        object.__setattr__(self, "observed_at", _int(self.observed_at, field_name="observed_at"))
        if self.source_profile_digest == self.target_profile_digest:
            raise LongRangeHealthError("portability drill requires distinct storage profiles")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "escrow_manifest_digest": self.escrow_manifest_digest,
            "source_profile_digest": self.source_profile_digest,
            "target_profile_digest": self.target_profile_digest,
            "artifact_count": self.artifact_count,
            "total_bytes": self.total_bytes,
            "migrated_blob_set_digest": self.migrated_blob_set_digest,
            "observed_at": self.observed_at,
        }

    @property
    def drill_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "drill_digest": self.drill_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StoragePortabilityDrillV1:
        expected = frozenset(
            {
                "schema",
                "case_id",
                "escrow_manifest_digest",
                "source_profile_digest",
                "target_profile_digest",
                "artifact_count",
                "total_bytes",
                "migrated_blob_set_digest",
                "observed_at",
                "drill_digest",
            }
        )
        _strict_keys(value, expected, field_name="portability drill")
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            escrow_manifest_digest=_digest(
                value.get("escrow_manifest_digest"), field_name="escrow_manifest_digest"
            ),
            source_profile_digest=_digest(
                value.get("source_profile_digest"), field_name="source_profile_digest"
            ),
            target_profile_digest=_digest(
                value.get("target_profile_digest"), field_name="target_profile_digest"
            ),
            artifact_count=_int(value.get("artifact_count"), field_name="artifact_count"),
            total_bytes=_int(value.get("total_bytes"), field_name="total_bytes"),
            migrated_blob_set_digest=_digest(
                value.get("migrated_blob_set_digest"), field_name="migrated_blob_set_digest"
            ),
            observed_at=_int(value.get("observed_at"), field_name="observed_at"),
        )
        if _digest(value.get("drill_digest"), field_name="drill_digest") != result.drill_digest:
            raise LongRangeHealthError("portability drill digest mismatch")
        return result


def run_storage_portability_drill_v1(
    *,
    long_range_manifest: LongRangeReplayManifestV1,
    escrow_manifest: ArtifactEscrowManifestV1,
    source: ArtifactEscrowBackendV1,
    target: ArtifactEscrowBackendV1,
    source_profile: StorageProfileV1,
    target_profile: StorageProfileV1,
    limits: EscrowLimitsV1,
    observed_at: int,
) -> StoragePortabilityDrillV1:
    """Migrate every preserved escrow blob and verify exact identity on the target backend."""

    escrow_manifest.verify_against(long_range_manifest)
    if source_profile.profile_digest == target_profile.profile_digest:
        raise LongRangeHealthError("portability drill requires distinct storage profiles")
    migrated: list[dict[str, object]] = []
    total_bytes = 0
    for binding in escrow_manifest.bindings:
        restored = migrate_verified_blob(binding.blob, source=source, target=target, limits=limits)
        migrated.append({"role": binding.role.value, "blob": restored.canonical_dict()})
        total_bytes += restored.size
    return StoragePortabilityDrillV1(
        case_id=escrow_manifest.case_id,
        escrow_manifest_digest=escrow_manifest.escrow_manifest_identity.digest,
        source_profile_digest=source_profile.profile_digest,
        target_profile_digest=target_profile.profile_digest,
        artifact_count=len(migrated),
        total_bytes=total_bytes,
        migrated_blob_set_digest=content_digest(migrated),
        observed_at=_int(observed_at, field_name="observed_at"),
    )


@dataclass(frozen=True, slots=True)
class LongRangeHealthReportV1:
    case_id: str
    evaluated_at: int
    freshness_policy_digest: str
    drift_report_digest: str
    crypto_state: HealthDimensionState
    portability_state: HealthDimensionState
    recovery_state: HealthDimensionState
    crypto_evidence_digest: str | None
    portability_evidence_digest: str | None
    recovery_evidence_digest: str | None
    state: LongRangeHealthState
    violations: tuple[str, ...]
    schema: str = LONG_RANGE_HEALTH_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LONG_RANGE_HEALTH_SCHEMA_V1:
            raise LongRangeHealthError(f"unsupported health report schema: {self.schema}")
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        object.__setattr__(self, "evaluated_at", _int(self.evaluated_at, field_name="evaluated_at"))
        object.__setattr__(
            self,
            "freshness_policy_digest",
            _digest(self.freshness_policy_digest, field_name="freshness_policy_digest"),
        )
        object.__setattr__(
            self, "drift_report_digest", _digest(self.drift_report_digest, field_name="drift_report_digest")
        )
        for name in ("crypto_state", "portability_state", "recovery_state"):
            if not isinstance(getattr(self, name), HealthDimensionState):
                raise LongRangeHealthError(f"unknown {name}")
        if not isinstance(self.state, LongRangeHealthState):
            raise LongRangeHealthError("unknown long-range health state")
        for name in (
            "crypto_evidence_digest",
            "portability_evidence_digest",
            "recovery_evidence_digest",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _digest(value, field_name=name))
        normalized = tuple(sorted({_text(item, field_name="violation") for item in self.violations}))
        object.__setattr__(self, "violations", normalized)
        if self.state is LongRangeHealthState.HEALTHY and normalized:
            raise LongRangeHealthError("HEALTHY report cannot contain violations")
        if self.state is not LongRangeHealthState.HEALTHY and not normalized:
            raise LongRangeHealthError("non-HEALTHY report requires violations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "evaluated_at": self.evaluated_at,
            "freshness_policy_digest": self.freshness_policy_digest,
            "drift_report_digest": self.drift_report_digest,
            "crypto_state": self.crypto_state.value,
            "portability_state": self.portability_state.value,
            "recovery_state": self.recovery_state.value,
            "crypto_evidence_digest": self.crypto_evidence_digest,
            "portability_evidence_digest": self.portability_evidence_digest,
            "recovery_evidence_digest": self.recovery_evidence_digest,
            "state": self.state.value,
            "violations": list(self.violations),
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "report_digest": self.report_digest}


def _freshness_state(*, observed_at: int, evaluated_at: int, max_age: int) -> HealthDimensionState:
    if observed_at > evaluated_at:
        raise LongRangeHealthError("health evidence timestamp is in the future")
    return (
        HealthDimensionState.FRESH
        if evaluated_at - observed_at <= max_age
        else HealthDimensionState.STALE
    )


def evaluate_long_range_health_v1(
    *,
    case_id: str,
    drift_report_digest: str,
    evaluated_at: int,
    policy: FreshnessPolicyV1,
    crypto_renewal: CryptoRenewalAttestationV1 | None,
    portability_drill: StoragePortabilityDrillV1 | None,
    recovery_manifest: RecoveryDrillManifestV1 | None,
    recovery_report: RecoveryConformanceReportV1 | None,
    recovery_observed_at: int | None,
) -> LongRangeHealthReportV1:
    """Evaluate current freshness explicitly; historical PASS evidence never implies health."""

    case_id = _text(case_id, field_name="case_id")
    evaluated_at = _int(evaluated_at, field_name="evaluated_at")
    violations: list[str] = []

    if crypto_renewal is None:
        crypto_state = HealthDimensionState.MISSING
        crypto_digest = None
        violations.append("crypto_renewal_missing")
    else:
        if crypto_renewal.case_id != case_id:
            raise LongRangeHealthError("crypto renewal case scope mismatch")
        crypto_state = _freshness_state(
            observed_at=crypto_renewal.renewed_at,
            evaluated_at=evaluated_at,
            max_age=policy.crypto_renewal_max_age_seconds,
        )
        crypto_digest = crypto_renewal.renewal_digest
        if crypto_state is HealthDimensionState.STALE:
            violations.append("crypto_renewal_stale")

    if portability_drill is None:
        portability_state = HealthDimensionState.MISSING
        portability_digest = None
        violations.append("portability_drill_missing")
    else:
        if portability_drill.case_id != case_id:
            raise LongRangeHealthError("portability drill case scope mismatch")
        portability_state = _freshness_state(
            observed_at=portability_drill.observed_at,
            evaluated_at=evaluated_at,
            max_age=policy.portability_max_age_seconds,
        )
        portability_digest = portability_drill.drill_digest
        if portability_state is HealthDimensionState.STALE:
            violations.append("portability_drill_stale")

    if recovery_manifest is None or recovery_report is None or recovery_observed_at is None:
        recovery_state = HealthDimensionState.MISSING
        recovery_digest = None
        violations.append("recovery_drill_missing")
    else:
        recovery_observed_at = _int(recovery_observed_at, field_name="recovery_observed_at")
        if recovery_manifest.case_id != case_id:
            raise LongRangeHealthError("recovery drill case scope mismatch")
        if recovery_report.manifest_digest != recovery_manifest.manifest_digest:
            raise LongRangeHealthError("recovery report is bound to a different manifest")
        recovery_digest = recovery_report.report_digest
        if recovery_report.state is RecoveryConformanceState.FAIL:
            recovery_state = HealthDimensionState.FAIL
            violations.append("recovery_conformance_fail")
        else:
            recovery_state = _freshness_state(
                observed_at=recovery_observed_at,
                evaluated_at=evaluated_at,
                max_age=policy.recovery_max_age_seconds,
            )
            if recovery_state is HealthDimensionState.STALE:
                violations.append("recovery_drill_stale")

    dimensions = (crypto_state, portability_state, recovery_state)
    if HealthDimensionState.FAIL in dimensions:
        state = LongRangeHealthState.DEGRADED
    elif HealthDimensionState.MISSING in dimensions:
        state = LongRangeHealthState.UNVERIFIABLE
    elif HealthDimensionState.STALE in dimensions:
        state = LongRangeHealthState.STALE
    else:
        state = LongRangeHealthState.HEALTHY

    return LongRangeHealthReportV1(
        case_id=case_id,
        evaluated_at=evaluated_at,
        freshness_policy_digest=policy.policy_digest,
        drift_report_digest=_digest(drift_report_digest, field_name="drift_report_digest"),
        crypto_state=crypto_state,
        portability_state=portability_state,
        recovery_state=recovery_state,
        crypto_evidence_digest=crypto_digest,
        portability_evidence_digest=portability_digest,
        recovery_evidence_digest=recovery_digest,
        state=state,
        violations=tuple(violations),
    )
