"""LRD-01G external durable escrow and multi-location restore conformance v1.

This module composes LRD-01C artifact escrow with DR-02 storage-profile identity.
It proves content-addressed replication and independent restore conformance across
two distinct declared locations. It does not claim ten-year durability, WORM,
geographic separation, or independent custody unless separately evidenced.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowBackendV1,
    ArtifactEscrowError,
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
    migrate_verified_blob,
)
from core.enterprise.recovery_continuity_v1 import StorageProfileV1
from core.p3.contracts import content_digest, require_hex_digest

DURABILITY_CAPABILITY_SCHEMA_V1 = "lukart.durability-capability-evidence.v1"
DURABLE_LOCATION_SCHEMA_V1 = "lukart.durable-escrow-location.v1"
MULTI_LOCATION_PLAN_SCHEMA_V1 = "lukart.multi-location-escrow-plan.v1"
REPLICATION_RECEIPT_SCHEMA_V1 = "lukart.multi-location-replication-receipt.v1"
LOCATION_RESTORE_REPORT_SCHEMA_V1 = "lukart.location-restore-report.v1"
MULTI_LOCATION_CONFORMANCE_SCHEMA_V1 = "lukart.multi-location-conformance-report.v1"


class DurableEscrowV1Error(ValueError):
    """Fail-closed LRD-01G contract violation."""


class DurabilityCapabilityV1(StrEnum):
    EXACT_BYTE_VERIFICATION = "EXACT_BYTE_VERIFICATION"
    IMMUTABLE_PUBLICATION = "IMMUTABLE_PUBLICATION"
    DELETE_PROTECTION = "DELETE_PROTECTION"
    WORM_OBJECT_LOCK = "WORM_OBJECT_LOCK"
    GEOGRAPHIC_SEPARATION = "GEOGRAPHIC_SEPARATION"
    INDEPENDENT_CREDENTIAL_DOMAIN = "INDEPENDENT_CREDENTIAL_DOMAIN"
    RETENTION_POLICY = "RETENTION_POLICY"


class CapabilityEvidenceStateV1(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNSUPPORTED = "UNSUPPORTED"


class RestoreConformanceStateV1(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ExternalDurabilityEvidenceStateV1(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


_REQUIRED_ENGINEERING_CAPABILITIES = frozenset(
    {
        DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION,
        DurabilityCapabilityV1.IMMUTABLE_PUBLICATION,
    }
)
_REQUIRED_EXTERNAL_CAPABILITIES = frozenset(
    {
        DurabilityCapabilityV1.DELETE_PROTECTION,
        DurabilityCapabilityV1.WORM_OBJECT_LOCK,
        DurabilityCapabilityV1.GEOGRAPHIC_SEPARATION,
        DurabilityCapabilityV1.INDEPENDENT_CREDENTIAL_DOMAIN,
        DurabilityCapabilityV1.RETENTION_POLICY,
    }
)
_FIXED_CAPABILITY_SET = frozenset(DurabilityCapabilityV1)


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DurableEscrowV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _nonnegative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DurableEscrowV1Error(f"{field_name} must be a nonnegative integer")
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(
            _text(value, field_name=field_name),
            field_name=field_name,
        )
    except ValueError as exc:
        raise DurableEscrowV1Error(str(exc)) from exc


def _optional_digest(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _digest(value, field_name=field_name)


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
    raise DurableEscrowV1Error(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


@dataclass(frozen=True, slots=True)
class DurabilityCapabilityEvidenceV1:
    capability: DurabilityCapabilityV1
    state: CapabilityEvidenceStateV1
    evidence_digest: str | None = None
    schema: str = DURABILITY_CAPABILITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != DURABILITY_CAPABILITY_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported durability capability schema: {self.schema}"
            )
        if not isinstance(self.capability, DurabilityCapabilityV1):
            raise DurableEscrowV1Error("unknown durability capability")
        if not isinstance(self.state, CapabilityEvidenceStateV1):
            raise DurableEscrowV1Error("unknown capability evidence state")
        normalized = _optional_digest(
            self.evidence_digest,
            field_name="capability evidence_digest",
        )
        object.__setattr__(self, "evidence_digest", normalized)
        if self.state is CapabilityEvidenceStateV1.VERIFIED and normalized is None:
            raise DurableEscrowV1Error(
                "VERIFIED durability capability requires exact evidence_digest"
            )
        if self.state is not CapabilityEvidenceStateV1.VERIFIED and normalized is not None:
            raise DurableEscrowV1Error(
                "non-VERIFIED durability capability cannot carry evidence_digest"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "capability": self.capability.value,
            "state": self.state.value,
            "evidence_digest": self.evidence_digest,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> DurabilityCapabilityEvidenceV1:
        _strict_keys(
            value,
            expected=frozenset(
                {"schema", "capability", "state", "evidence_digest"}
            ),
            field_name="durability capability evidence",
        )
        try:
            capability = DurabilityCapabilityV1(
                _text(value.get("capability"), field_name="capability")
            )
            state = CapabilityEvidenceStateV1(
                _text(value.get("state"), field_name="state")
            )
        except ValueError as exc:
            raise DurableEscrowV1Error(
                "unknown durability capability or evidence state"
            ) from exc
        return cls(
            schema=_text(value.get("schema"), field_name="schema"),
            capability=capability,
            state=state,
            evidence_digest=_optional_digest(
                value.get("evidence_digest"),
                field_name="evidence_digest",
            ),
        )


@dataclass(frozen=True, slots=True)
class DurableEscrowLocationV1:
    storage_profile_digest: str
    location_id: str
    failure_domain_id: str
    credential_domain_id: str
    capabilities: tuple[DurabilityCapabilityEvidenceV1, ...]
    schema: str = DURABLE_LOCATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != DURABLE_LOCATION_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported durable location schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "storage_profile_digest",
            _digest(self.storage_profile_digest, field_name="storage_profile_digest"),
        )
        for name in ("location_id", "failure_domain_id", "credential_domain_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), field_name=name),
            )
        ordered = tuple(sorted(self.capabilities, key=lambda item: item.capability.value))
        capability_set = {item.capability for item in ordered}
        if capability_set != _FIXED_CAPABILITY_SET or len(ordered) != len(
            _FIXED_CAPABILITY_SET
        ):
            raise DurableEscrowV1Error(
                "durable location must contain the fixed complete capability inventory"
            )
        by_capability = {item.capability: item for item in ordered}
        for capability in _REQUIRED_ENGINEERING_CAPABILITIES:
            if (
                by_capability[capability].state
                is not CapabilityEvidenceStateV1.VERIFIED
            ):
                raise DurableEscrowV1Error(
                    f"engineering capability must be VERIFIED: {capability.value}"
                )
        object.__setattr__(self, "capabilities", ordered)

    @classmethod
    def build(
        cls,
        *,
        storage_profile: StorageProfileV1,
        location_id: str,
        failure_domain_id: str,
        credential_domain_id: str,
        capabilities: Sequence[DurabilityCapabilityEvidenceV1],
    ) -> DurableEscrowLocationV1:
        return cls(
            storage_profile_digest=storage_profile.profile_digest,
            location_id=location_id,
            failure_domain_id=failure_domain_id,
            credential_domain_id=credential_domain_id,
            capabilities=tuple(capabilities),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "storage_profile_digest": self.storage_profile_digest,
            "location_id": self.location_id,
            "failure_domain_id": self.failure_domain_id,
            "credential_domain_id": self.credential_domain_id,
            "capabilities": [item.canonical_dict() for item in self.capabilities],
        }

    @property
    def location_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "location_digest": self.location_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> DurableEscrowLocationV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "storage_profile_digest",
                    "location_id",
                    "failure_domain_id",
                    "credential_domain_id",
                    "capabilities",
                    "location_digest",
                }
            ),
            field_name="durable escrow location",
        )
        raw_capabilities = value.get("capabilities")
        if not isinstance(raw_capabilities, list):
            raise DurableEscrowV1Error("capabilities must be a list")
        capabilities: list[DurabilityCapabilityEvidenceV1] = []
        for raw in raw_capabilities:
            if not isinstance(raw, Mapping):
                raise DurableEscrowV1Error("capability evidence must be an object")
            capabilities.append(
                DurabilityCapabilityEvidenceV1.from_dict(
                    cast(Mapping[str, object], raw)
                )
            )
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            storage_profile_digest=_digest(
                value.get("storage_profile_digest"),
                field_name="storage_profile_digest",
            ),
            location_id=_text(value.get("location_id"), field_name="location_id"),
            failure_domain_id=_text(
                value.get("failure_domain_id"),
                field_name="failure_domain_id",
            ),
            credential_domain_id=_text(
                value.get("credential_domain_id"),
                field_name="credential_domain_id",
            ),
            capabilities=tuple(capabilities),
        )
        recorded = _digest(
            value.get("location_digest"),
            field_name="location_digest",
        )
        if recorded != result.location_digest:
            raise DurableEscrowV1Error("durable location digest mismatch")
        return result

    def external_evidence_complete(self) -> bool:
        by_capability = {item.capability: item for item in self.capabilities}
        return all(
            by_capability[capability].state is CapabilityEvidenceStateV1.VERIFIED
            for capability in _REQUIRED_EXTERNAL_CAPABILITIES
        )


@dataclass(frozen=True, slots=True)
class MultiLocationEscrowPlanV1:
    case_id: str
    escrow_manifest_digest: str
    source_location_digest: str
    target_location_digest: str
    blob_set_digest: str
    blob_count: int
    total_bytes: int
    schema: str = MULTI_LOCATION_PLAN_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != MULTI_LOCATION_PLAN_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported multi-location plan schema: {self.schema}"
            )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "escrow_manifest_digest",
            "source_location_digest",
            "target_location_digest",
            "blob_set_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        object.__setattr__(
            self,
            "blob_count",
            _nonnegative_int(self.blob_count, field_name="blob_count"),
        )
        object.__setattr__(
            self,
            "total_bytes",
            _nonnegative_int(self.total_bytes, field_name="total_bytes"),
        )
        if self.blob_count == 0:
            raise DurableEscrowV1Error("multi-location plan requires preserved blobs")
        if self.source_location_digest == self.target_location_digest:
            raise DurableEscrowV1Error("multi-location plan requires distinct locations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "escrow_manifest_digest": self.escrow_manifest_digest,
            "source_location_digest": self.source_location_digest,
            "target_location_digest": self.target_location_digest,
            "blob_set_digest": self.blob_set_digest,
            "blob_count": self.blob_count,
            "total_bytes": self.total_bytes,
        }

    @property
    def plan_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "plan_digest": self.plan_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MultiLocationEscrowPlanV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "case_id",
                    "escrow_manifest_digest",
                    "source_location_digest",
                    "target_location_digest",
                    "blob_set_digest",
                    "blob_count",
                    "total_bytes",
                    "plan_digest",
                }
            ),
            field_name="multi-location plan",
        )
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            escrow_manifest_digest=_digest(
                value.get("escrow_manifest_digest"),
                field_name="escrow_manifest_digest",
            ),
            source_location_digest=_digest(
                value.get("source_location_digest"),
                field_name="source_location_digest",
            ),
            target_location_digest=_digest(
                value.get("target_location_digest"),
                field_name="target_location_digest",
            ),
            blob_set_digest=_digest(
                value.get("blob_set_digest"),
                field_name="blob_set_digest",
            ),
            blob_count=_nonnegative_int(
                value.get("blob_count"),
                field_name="blob_count",
            ),
            total_bytes=_nonnegative_int(
                value.get("total_bytes"),
                field_name="total_bytes",
            ),
        )
        recorded = _digest(value.get("plan_digest"), field_name="plan_digest")
        if recorded != result.plan_digest:
            raise DurableEscrowV1Error("multi-location plan digest mismatch")
        return result


def _blob_set_digest(escrow_manifest: ArtifactEscrowManifestV1) -> str:
    return content_digest(
        [
            {
                "role": binding.role.value,
                "logical_identity": binding.logical_identity.canonical_dict(),
                "blob": binding.blob.canonical_dict(),
            }
            for binding in escrow_manifest.bindings
        ]
    )


def _validate_location_separation(
    source: DurableEscrowLocationV1,
    target: DurableEscrowLocationV1,
) -> None:
    if source.location_digest == target.location_digest:
        raise DurableEscrowV1Error("source and target location identities must differ")
    if source.storage_profile_digest == target.storage_profile_digest:
        raise DurableEscrowV1Error("source and target storage profiles must differ")
    if source.location_id == target.location_id:
        raise DurableEscrowV1Error("source and target location_id must differ")
    if source.failure_domain_id == target.failure_domain_id:
        raise DurableEscrowV1Error("source and target failure domains must differ")
    if source.credential_domain_id == target.credential_domain_id:
        raise DurableEscrowV1Error("source and target credential domains must differ")


def build_multi_location_plan_v1(
    *,
    expected_case_id: str,
    escrow_manifest: ArtifactEscrowManifestV1,
    source_location: DurableEscrowLocationV1,
    target_location: DurableEscrowLocationV1,
) -> MultiLocationEscrowPlanV1:
    case_id = _text(expected_case_id, field_name="expected_case_id")
    if escrow_manifest.case_id != case_id:
        raise DurableEscrowV1Error("escrow tenant/case scope mismatch")
    _validate_location_separation(source_location, target_location)
    return MultiLocationEscrowPlanV1(
        case_id=case_id,
        escrow_manifest_digest=escrow_manifest.escrow_manifest_identity.digest,
        source_location_digest=source_location.location_digest,
        target_location_digest=target_location.location_digest,
        blob_set_digest=_blob_set_digest(escrow_manifest),
        blob_count=len(escrow_manifest.bindings),
        total_bytes=sum(binding.blob.size for binding in escrow_manifest.bindings),
    )


@dataclass(frozen=True, slots=True)
class MultiLocationReplicationReceiptV1:
    plan_digest: str
    case_id: str
    escrow_manifest_digest: str
    source_location_digest: str
    target_location_digest: str
    blob_set_digest: str
    replicated_blob_count: int
    replicated_bytes: int
    schema: str = REPLICATION_RECEIPT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REPLICATION_RECEIPT_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported replication receipt schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "plan_digest",
            _digest(self.plan_digest, field_name="plan_digest"),
        )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "escrow_manifest_digest",
            "source_location_digest",
            "target_location_digest",
            "blob_set_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        object.__setattr__(
            self,
            "replicated_blob_count",
            _nonnegative_int(
                self.replicated_blob_count,
                field_name="replicated_blob_count",
            ),
        )
        object.__setattr__(
            self,
            "replicated_bytes",
            _nonnegative_int(self.replicated_bytes, field_name="replicated_bytes"),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "plan_digest": self.plan_digest,
            "case_id": self.case_id,
            "escrow_manifest_digest": self.escrow_manifest_digest,
            "source_location_digest": self.source_location_digest,
            "target_location_digest": self.target_location_digest,
            "blob_set_digest": self.blob_set_digest,
            "replicated_blob_count": self.replicated_blob_count,
            "replicated_bytes": self.replicated_bytes,
        }

    @property
    def receipt_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "receipt_digest": self.receipt_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> MultiLocationReplicationReceiptV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "plan_digest",
                    "case_id",
                    "escrow_manifest_digest",
                    "source_location_digest",
                    "target_location_digest",
                    "blob_set_digest",
                    "replicated_blob_count",
                    "replicated_bytes",
                    "receipt_digest",
                }
            ),
            field_name="replication receipt",
        )
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            plan_digest=_digest(value.get("plan_digest"), field_name="plan_digest"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            escrow_manifest_digest=_digest(
                value.get("escrow_manifest_digest"),
                field_name="escrow_manifest_digest",
            ),
            source_location_digest=_digest(
                value.get("source_location_digest"),
                field_name="source_location_digest",
            ),
            target_location_digest=_digest(
                value.get("target_location_digest"),
                field_name="target_location_digest",
            ),
            blob_set_digest=_digest(
                value.get("blob_set_digest"),
                field_name="blob_set_digest",
            ),
            replicated_blob_count=_nonnegative_int(
                value.get("replicated_blob_count"),
                field_name="replicated_blob_count",
            ),
            replicated_bytes=_nonnegative_int(
                value.get("replicated_bytes"),
                field_name="replicated_bytes",
            ),
        )
        recorded = _digest(
            value.get("receipt_digest"),
            field_name="receipt_digest",
        )
        if recorded != result.receipt_digest:
            raise DurableEscrowV1Error("replication receipt digest mismatch")
        return result


def replicate_escrow_manifest_v1(
    *,
    plan: MultiLocationEscrowPlanV1,
    escrow_manifest: ArtifactEscrowManifestV1,
    source_location: DurableEscrowLocationV1,
    target_location: DurableEscrowLocationV1,
    source_backend: ArtifactEscrowBackendV1,
    target_backend: ArtifactEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> MultiLocationReplicationReceiptV1:
    _validate_location_separation(source_location, target_location)
    if escrow_manifest.case_id != plan.case_id:
        raise DurableEscrowV1Error("replication case scope mismatch")
    if (
        escrow_manifest.escrow_manifest_identity.digest
        != plan.escrow_manifest_digest
    ):
        raise DurableEscrowV1Error("replication escrow manifest identity mismatch")
    if source_location.location_digest != plan.source_location_digest:
        raise DurableEscrowV1Error("source location substitution rejected")
    if target_location.location_digest != plan.target_location_digest:
        raise DurableEscrowV1Error("target location substitution rejected")
    if _blob_set_digest(escrow_manifest) != plan.blob_set_digest:
        raise DurableEscrowV1Error("replication blob-set identity mismatch")
    if len(escrow_manifest.bindings) != plan.blob_count:
        raise DurableEscrowV1Error("replication blob-count mismatch")

    total_bytes = 0
    try:
        for binding in escrow_manifest.bindings:
            migrated = migrate_verified_blob(
                binding.blob,
                source=source_backend,
                target=target_backend,
                limits=limits,
            )
            if migrated != binding.blob:
                raise DurableEscrowV1Error(
                    f"replication changed blob identity for role {binding.role.value}"
                )
            total_bytes += migrated.size
    except ArtifactEscrowError as exc:
        raise DurableEscrowV1Error("verified multi-location replication failed") from exc

    if total_bytes != plan.total_bytes:
        raise DurableEscrowV1Error("replicated byte-count mismatch")
    return MultiLocationReplicationReceiptV1(
        plan_digest=plan.plan_digest,
        case_id=plan.case_id,
        escrow_manifest_digest=plan.escrow_manifest_digest,
        source_location_digest=source_location.location_digest,
        target_location_digest=target_location.location_digest,
        blob_set_digest=plan.blob_set_digest,
        replicated_blob_count=plan.blob_count,
        replicated_bytes=total_bytes,
    )


@dataclass(frozen=True, slots=True)
class LocationRestoreReportV1:
    case_id: str
    escrow_manifest_digest: str
    location_digest: str
    blob_set_digest: str
    expected_blob_count: int
    verified_blob_count: int
    expected_bytes: int
    verified_bytes: int
    state: RestoreConformanceStateV1
    violations: tuple[str, ...]
    schema: str = LOCATION_RESTORE_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LOCATION_RESTORE_REPORT_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported location restore report schema: {self.schema}"
            )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "escrow_manifest_digest",
            "location_digest",
            "blob_set_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        for name in (
            "expected_blob_count",
            "verified_blob_count",
            "expected_bytes",
            "verified_bytes",
        ):
            object.__setattr__(
                self,
                name,
                _nonnegative_int(getattr(self, name), field_name=name),
            )
        if not isinstance(self.state, RestoreConformanceStateV1):
            raise DurableEscrowV1Error("unknown restore conformance state")
        normalized = tuple(
            sorted({_text(item, field_name="violation") for item in self.violations})
        )
        object.__setattr__(self, "violations", normalized)
        counts_match = self.expected_blob_count == self.verified_blob_count
        bytes_match = self.expected_bytes == self.verified_bytes
        if self.state is RestoreConformanceStateV1.PASS:
            if normalized or not counts_match or not bytes_match:
                raise DurableEscrowV1Error(
                    "PASS restore report requires complete verified identity"
                )
        elif not normalized:
            raise DurableEscrowV1Error("FAIL restore report requires violations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "escrow_manifest_digest": self.escrow_manifest_digest,
            "location_digest": self.location_digest,
            "blob_set_digest": self.blob_set_digest,
            "expected_blob_count": self.expected_blob_count,
            "verified_blob_count": self.verified_blob_count,
            "expected_bytes": self.expected_bytes,
            "verified_bytes": self.verified_bytes,
            "state": self.state.value,
            "violations": list(self.violations),
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "report_digest": self.report_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> LocationRestoreReportV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "case_id",
                    "escrow_manifest_digest",
                    "location_digest",
                    "blob_set_digest",
                    "expected_blob_count",
                    "verified_blob_count",
                    "expected_bytes",
                    "verified_bytes",
                    "state",
                    "violations",
                    "report_digest",
                }
            ),
            field_name="location restore report",
        )
        raw_violations = value.get("violations")
        if not isinstance(raw_violations, list):
            raise DurableEscrowV1Error("violations must be a list")
        try:
            state = RestoreConformanceStateV1(
                _text(value.get("state"), field_name="state")
            )
        except ValueError as exc:
            raise DurableEscrowV1Error("unknown restore conformance state") from exc
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            escrow_manifest_digest=_digest(
                value.get("escrow_manifest_digest"),
                field_name="escrow_manifest_digest",
            ),
            location_digest=_digest(
                value.get("location_digest"),
                field_name="location_digest",
            ),
            blob_set_digest=_digest(
                value.get("blob_set_digest"),
                field_name="blob_set_digest",
            ),
            expected_blob_count=_nonnegative_int(
                value.get("expected_blob_count"),
                field_name="expected_blob_count",
            ),
            verified_blob_count=_nonnegative_int(
                value.get("verified_blob_count"),
                field_name="verified_blob_count",
            ),
            expected_bytes=_nonnegative_int(
                value.get("expected_bytes"),
                field_name="expected_bytes",
            ),
            verified_bytes=_nonnegative_int(
                value.get("verified_bytes"),
                field_name="verified_bytes",
            ),
            state=state,
            violations=tuple(
                _text(item, field_name="violation") for item in raw_violations
            ),
        )
        recorded = _digest(value.get("report_digest"), field_name="report_digest")
        if recorded != result.report_digest:
            raise DurableEscrowV1Error("location restore report digest mismatch")
        return result


def verify_location_restore_v1(
    *,
    expected_case_id: str,
    escrow_manifest: ArtifactEscrowManifestV1,
    location: DurableEscrowLocationV1,
    backend: ArtifactEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> LocationRestoreReportV1:
    case_id = _text(expected_case_id, field_name="expected_case_id")
    if escrow_manifest.case_id != case_id:
        raise DurableEscrowV1Error("restore tenant/case scope mismatch")
    verified_count = 0
    verified_bytes = 0
    violations: list[str] = []
    for binding in escrow_manifest.bindings:
        try:
            data = backend.read(binding.blob, limits=limits)
        except ArtifactEscrowError:
            violations.append(f"{binding.role.value}:verified_read_failed")
            continue
        if len(data) != binding.blob.size:
            violations.append(f"{binding.role.value}:verified_size_mismatch")
            continue
        verified_count += 1
        verified_bytes += len(data)
    state = (
        RestoreConformanceStateV1.PASS
        if not violations
        else RestoreConformanceStateV1.FAIL
    )
    return LocationRestoreReportV1(
        case_id=case_id,
        escrow_manifest_digest=escrow_manifest.escrow_manifest_identity.digest,
        location_digest=location.location_digest,
        blob_set_digest=_blob_set_digest(escrow_manifest),
        expected_blob_count=len(escrow_manifest.bindings),
        verified_blob_count=verified_count,
        expected_bytes=sum(binding.blob.size for binding in escrow_manifest.bindings),
        verified_bytes=verified_bytes,
        state=state,
        violations=tuple(violations),
    )


@dataclass(frozen=True, slots=True)
class MultiLocationConformanceReportV1:
    plan_digest: str
    replication_receipt_digest: str
    source_restore_report_digest: str
    target_restore_report_digest: str
    state: RestoreConformanceStateV1
    external_durability_evidence: ExternalDurabilityEvidenceStateV1
    ten_year_durability_claim: bool
    violations: tuple[str, ...]
    schema: str = MULTI_LOCATION_CONFORMANCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != MULTI_LOCATION_CONFORMANCE_SCHEMA_V1:
            raise DurableEscrowV1Error(
                f"unsupported multi-location conformance schema: {self.schema}"
            )
        for name in (
            "plan_digest",
            "replication_receipt_digest",
            "source_restore_report_digest",
            "target_restore_report_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        if not isinstance(self.state, RestoreConformanceStateV1):
            raise DurableEscrowV1Error("unknown aggregate conformance state")
        if not isinstance(
            self.external_durability_evidence,
            ExternalDurabilityEvidenceStateV1,
        ):
            raise DurableEscrowV1Error("unknown external durability evidence state")
        if self.ten_year_durability_claim:
            raise DurableEscrowV1Error(
                "LRD-01G engineering evidence cannot claim ten-year durability"
            )
        normalized = tuple(
            sorted({_text(item, field_name="violation") for item in self.violations})
        )
        object.__setattr__(self, "violations", normalized)
        if self.state is RestoreConformanceStateV1.PASS and normalized:
            raise DurableEscrowV1Error("PASS aggregate report cannot contain violations")
        if self.state is RestoreConformanceStateV1.FAIL and not normalized:
            raise DurableEscrowV1Error("FAIL aggregate report requires violations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "plan_digest": self.plan_digest,
            "replication_receipt_digest": self.replication_receipt_digest,
            "source_restore_report_digest": self.source_restore_report_digest,
            "target_restore_report_digest": self.target_restore_report_digest,
            "state": self.state.value,
            "external_durability_evidence": self.external_durability_evidence.value,
            "ten_year_durability_claim": self.ten_year_durability_claim,
            "violations": list(self.violations),
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "report_digest": self.report_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> MultiLocationConformanceReportV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "plan_digest",
                    "replication_receipt_digest",
                    "source_restore_report_digest",
                    "target_restore_report_digest",
                    "state",
                    "external_durability_evidence",
                    "ten_year_durability_claim",
                    "violations",
                    "report_digest",
                }
            ),
            field_name="multi-location conformance report",
        )
        raw_violations = value.get("violations")
        if not isinstance(raw_violations, list):
            raise DurableEscrowV1Error("violations must be a list")
        raw_ten_year = value.get("ten_year_durability_claim")
        if not isinstance(raw_ten_year, bool):
            raise DurableEscrowV1Error("ten_year_durability_claim must be boolean")
        try:
            state = RestoreConformanceStateV1(
                _text(value.get("state"), field_name="state")
            )
            external_state = ExternalDurabilityEvidenceStateV1(
                _text(
                    value.get("external_durability_evidence"),
                    field_name="external_durability_evidence",
                )
            )
        except ValueError as exc:
            raise DurableEscrowV1Error("unknown aggregate conformance enum") from exc
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            plan_digest=_digest(value.get("plan_digest"), field_name="plan_digest"),
            replication_receipt_digest=_digest(
                value.get("replication_receipt_digest"),
                field_name="replication_receipt_digest",
            ),
            source_restore_report_digest=_digest(
                value.get("source_restore_report_digest"),
                field_name="source_restore_report_digest",
            ),
            target_restore_report_digest=_digest(
                value.get("target_restore_report_digest"),
                field_name="target_restore_report_digest",
            ),
            state=state,
            external_durability_evidence=external_state,
            ten_year_durability_claim=raw_ten_year,
            violations=tuple(
                _text(item, field_name="violation") for item in raw_violations
            ),
        )
        recorded = _digest(value.get("report_digest"), field_name="report_digest")
        if recorded != result.report_digest:
            raise DurableEscrowV1Error("multi-location conformance report digest mismatch")
        return result


def build_multi_location_conformance_report_v1(
    *,
    plan: MultiLocationEscrowPlanV1,
    replication_receipt: MultiLocationReplicationReceiptV1,
    source_location: DurableEscrowLocationV1,
    target_location: DurableEscrowLocationV1,
    source_restore: LocationRestoreReportV1,
    target_restore: LocationRestoreReportV1,
) -> MultiLocationConformanceReportV1:
    _validate_location_separation(source_location, target_location)
    if replication_receipt.plan_digest != plan.plan_digest:
        raise DurableEscrowV1Error("replication receipt plan substitution rejected")
    if (
        replication_receipt.escrow_manifest_digest
        != plan.escrow_manifest_digest
        or replication_receipt.blob_set_digest != plan.blob_set_digest
        or replication_receipt.replicated_blob_count != plan.blob_count
        or replication_receipt.replicated_bytes != plan.total_bytes
    ):
        raise DurableEscrowV1Error("replication receipt does not satisfy exact plan")
    if source_restore.case_id != plan.case_id or target_restore.case_id != plan.case_id:
        raise DurableEscrowV1Error("restore report case substitution rejected")
    if (
        source_restore.escrow_manifest_digest != plan.escrow_manifest_digest
        or target_restore.escrow_manifest_digest != plan.escrow_manifest_digest
        or source_restore.blob_set_digest != plan.blob_set_digest
        or target_restore.blob_set_digest != plan.blob_set_digest
    ):
        raise DurableEscrowV1Error("restore report escrow/blob-set substitution rejected")
    if source_restore.location_digest != source_location.location_digest:
        raise DurableEscrowV1Error("source restore location substitution rejected")
    if target_restore.location_digest != target_location.location_digest:
        raise DurableEscrowV1Error("target restore location substitution rejected")

    violations: list[str] = []
    if source_restore.state is not RestoreConformanceStateV1.PASS:
        violations.append("source_location_restore_failed")
    if target_restore.state is not RestoreConformanceStateV1.PASS:
        violations.append("target_location_restore_failed")
    state = (
        RestoreConformanceStateV1.PASS
        if not violations
        else RestoreConformanceStateV1.FAIL
    )
    external_state = (
        ExternalDurabilityEvidenceStateV1.COMPLETE
        if source_location.external_evidence_complete()
        and target_location.external_evidence_complete()
        else ExternalDurabilityEvidenceStateV1.INCOMPLETE
    )
    return MultiLocationConformanceReportV1(
        plan_digest=plan.plan_digest,
        replication_receipt_digest=replication_receipt.receipt_digest,
        source_restore_report_digest=source_restore.report_digest,
        target_restore_report_digest=target_restore.report_digest,
        state=state,
        external_durability_evidence=external_state,
        ten_year_durability_claim=False,
        violations=tuple(violations),
    )
