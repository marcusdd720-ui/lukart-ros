"""LRD-01F post-quantum migration readiness and archival renewal planning.

This module composes CRY-01 and LRD-01E evidence. It deliberately does not add a
post-quantum signature implementation, private-key storage, trust-root promotion,
Canonical Case Ledger write authority, or a release path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.crypto_agility_v1 import CryptoAlgorithmV1, CryptoTrustSetV1
from core.long_range_health_v1 import LongRangeHealthReportV1, LongRangeHealthState
from core.p3.contracts import content_digest, require_hex_digest

PQC_TARGET_FAMILY_SCHEMA_V1 = "lukart.lrd-pqc-target-family.v1"
PQC_MIGRATION_POLICY_SCHEMA_V1 = "lukart.lrd-pqc-migration-policy.v1"
PQC_SIGNATURE_SURFACE_SCHEMA_V1 = "lukart.lrd-pqc-signature-surface.v1"
PQC_READINESS_REPORT_SCHEMA_V1 = "lukart.lrd-pqc-readiness-report.v1"
ARCHIVAL_RENEWAL_PLAN_SCHEMA_V1 = "lukart.lrd-archival-renewal-plan.v1"


class PostQuantumReadinessError(ValueError):
    """Fail-closed LRD-01F contract violation."""


class PqcTargetFamilyV1(StrEnum):
    ML_DSA = "ML-DSA"
    SLH_DSA = "SLH-DSA"


class PqcTargetRoleV1(StrEnum):
    PRIMARY_CANDIDATE = "PRIMARY_CANDIDATE"
    DIVERSITY_CANDIDATE = "DIVERSITY_CANDIDATE"


class PqcReadinessStateV1(StrEnum):
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
    BLOCKED_CURRENT_HEALTH = "BLOCKED_CURRENT_HEALTH"


class ArchivalRenewalPlanStateV1(StrEnum):
    READY_FOR_ADAPTER_IMPLEMENTATION = "READY_FOR_ADAPTER_IMPLEMENTATION"
    BLOCKED_CURRENT_HEALTH = "BLOCKED_CURRENT_HEALTH"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PostQuantumReadinessError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PostQuantumReadinessError(f"{field_name} must be a nonnegative integer")
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(
            _text(value, field_name=field_name),
            field_name=field_name,
        )
    except ValueError as exc:
        raise PostQuantumReadinessError(str(exc)) from exc


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
    raise PostQuantumReadinessError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


_STANDARD_BY_FAMILY = {
    PqcTargetFamilyV1.ML_DSA: "NIST-FIPS-204",
    PqcTargetFamilyV1.SLH_DSA: "NIST-FIPS-205",
}
_ROLE_BY_FAMILY = {
    PqcTargetFamilyV1.ML_DSA: PqcTargetRoleV1.PRIMARY_CANDIDATE,
    PqcTargetFamilyV1.SLH_DSA: PqcTargetRoleV1.DIVERSITY_CANDIDATE,
}


@dataclass(frozen=True, slots=True)
class PqcTargetFamilyProfileV1:
    family: PqcTargetFamilyV1
    standard_id: str
    role: PqcTargetRoleV1
    adapter_required: bool = True
    operational_parameter_set: str | None = None
    schema: str = PQC_TARGET_FAMILY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PQC_TARGET_FAMILY_SCHEMA_V1:
            raise PostQuantumReadinessError(
                f"unsupported PQC target-family schema: {self.schema}"
            )
        if not isinstance(self.family, PqcTargetFamilyV1):
            raise PostQuantumReadinessError("unknown PQC target family")
        if not isinstance(self.role, PqcTargetRoleV1):
            raise PostQuantumReadinessError("unknown PQC target role")
        expected_standard = _STANDARD_BY_FAMILY[self.family]
        if _text(self.standard_id, field_name="standard_id") != expected_standard:
            raise PostQuantumReadinessError(
                "PQC target family is bound to an unexpected standard"
            )
        if self.role is not _ROLE_BY_FAMILY[self.family]:
            raise PostQuantumReadinessError("PQC target role does not match fixed registry")
        if self.adapter_required is not True:
            raise PostQuantumReadinessError(
                "LRD-01F cannot claim a validated PQC adapter"
            )
        if self.operational_parameter_set is not None:
            raise PostQuantumReadinessError(
                "operational PQC parameter set requires a separately validated adapter stage"
            )

    @classmethod
    def candidate(cls, family: PqcTargetFamilyV1) -> PqcTargetFamilyProfileV1:
        return cls(
            family=family,
            standard_id=_STANDARD_BY_FAMILY[family],
            role=_ROLE_BY_FAMILY[family],
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "family": self.family.value,
            "standard_id": self.standard_id,
            "role": self.role.value,
            "adapter_required": self.adapter_required,
            "operational_parameter_set": self.operational_parameter_set,
        }

    @property
    def profile_digest(self) -> str:
        return content_digest(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PqcTargetFamilyProfileV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "family",
                    "standard_id",
                    "role",
                    "adapter_required",
                    "operational_parameter_set",
                }
            ),
            field_name="PQC target-family profile",
        )
        try:
            family = PqcTargetFamilyV1(
                _text(value.get("family"), field_name="family")
            )
            role = PqcTargetRoleV1(_text(value.get("role"), field_name="role"))
        except ValueError as exc:
            raise PostQuantumReadinessError("unknown PQC target family or role") from exc
        adapter_required = value.get("adapter_required")
        if not isinstance(adapter_required, bool):
            raise PostQuantumReadinessError("adapter_required must be boolean")
        parameter_raw = value.get("operational_parameter_set")
        parameter = (
            None
            if parameter_raw is None
            else _text(parameter_raw, field_name="operational_parameter_set")
        )
        return cls(
            schema=_text(value.get("schema"), field_name="schema"),
            family=family,
            standard_id=_text(value.get("standard_id"), field_name="standard_id"),
            role=role,
            adapter_required=adapter_required,
            operational_parameter_set=parameter,
        )


def default_pqc_targets_v1() -> tuple[PqcTargetFamilyProfileV1, ...]:
    return (
        PqcTargetFamilyProfileV1.candidate(PqcTargetFamilyV1.ML_DSA),
        PqcTargetFamilyProfileV1.candidate(PqcTargetFamilyV1.SLH_DSA),
    )


@dataclass(frozen=True, slots=True)
class PqcMigrationPolicyV1:
    targets: tuple[PqcTargetFamilyProfileV1, ...]
    preserve_original_evidence: bool = True
    additive_renewal_only: bool = True
    dual_verification_before_cutover: bool = True
    schema: str = PQC_MIGRATION_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PQC_MIGRATION_POLICY_SCHEMA_V1:
            raise PostQuantumReadinessError(
                f"unsupported PQC migration policy schema: {self.schema}"
            )
        ordered = tuple(sorted(self.targets, key=lambda item: item.family.value))
        expected = tuple(
            sorted(default_pqc_targets_v1(), key=lambda item: item.family.value)
        )
        if ordered != expected:
            raise PostQuantumReadinessError(
                "PQC target registry cannot be reduced, expanded or reinterpreted in v1"
            )
        for name in (
            "preserve_original_evidence",
            "additive_renewal_only",
            "dual_verification_before_cutover",
        ):
            if getattr(self, name) is not True:
                raise PostQuantumReadinessError(f"{name} must remain enabled")
        object.__setattr__(self, "targets", ordered)

    @classmethod
    def default(cls) -> PqcMigrationPolicyV1:
        return cls(targets=default_pqc_targets_v1())

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "targets": [item.canonical_dict() for item in self.targets],
            "preserve_original_evidence": self.preserve_original_evidence,
            "additive_renewal_only": self.additive_renewal_only,
            "dual_verification_before_cutover": self.dual_verification_before_cutover,
        }

    @property
    def policy_digest(self) -> str:
        return content_digest(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PqcMigrationPolicyV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "targets",
                    "preserve_original_evidence",
                    "additive_renewal_only",
                    "dual_verification_before_cutover",
                    "policy_digest",
                }
            ),
            field_name="PQC migration policy",
        )
        raw_targets = value.get("targets")
        if not isinstance(raw_targets, list):
            raise PostQuantumReadinessError("targets must be a list")
        targets: list[PqcTargetFamilyProfileV1] = []
        for raw in raw_targets:
            if not isinstance(raw, Mapping):
                raise PostQuantumReadinessError("PQC target profile must be an object")
            targets.append(PqcTargetFamilyProfileV1.from_dict(raw))
        for name in (
            "preserve_original_evidence",
            "additive_renewal_only",
            "dual_verification_before_cutover",
        ):
            if not isinstance(value.get(name), bool):
                raise PostQuantumReadinessError(f"{name} must be boolean")
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            targets=tuple(targets),
            preserve_original_evidence=bool(value.get("preserve_original_evidence")),
            additive_renewal_only=bool(value.get("additive_renewal_only")),
            dual_verification_before_cutover=bool(
                value.get("dual_verification_before_cutover")
            ),
        )
        recorded = _digest(value.get("policy_digest"), field_name="policy_digest")
        if recorded != result.policy_digest:
            raise PostQuantumReadinessError("PQC migration policy digest mismatch")
        return result

    def serialized(self) -> dict[str, object]:
        return {**self.canonical_dict(), "policy_digest": self.policy_digest}


@dataclass(frozen=True, slots=True)
class SignatureSurfaceV1:
    key_id: str
    key_digest: str
    algorithm: CryptoAlgorithmV1
    status: str
    allowed_purposes: tuple[str, ...]
    schema: str = PQC_SIGNATURE_SURFACE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PQC_SIGNATURE_SURFACE_SCHEMA_V1:
            raise PostQuantumReadinessError(
                f"unsupported signature-surface schema: {self.schema}"
            )
        object.__setattr__(self, "key_id", _text(self.key_id, field_name="key_id"))
        object.__setattr__(
            self,
            "key_digest",
            _digest(self.key_digest, field_name="key_digest"),
        )
        if self.algorithm is not CryptoAlgorithmV1.ED25519:
            raise PostQuantumReadinessError(
                "current CRY-01 runtime supports only ED25519 signature surfaces"
            )
        object.__setattr__(self, "status", _text(self.status, field_name="status"))
        purposes = tuple(
            sorted(
                {
                    _text(item, field_name="allowed_purpose")
                    for item in self.allowed_purposes
                }
            )
        )
        if not purposes:
            raise PostQuantumReadinessError("signature surface requires allowed_purposes")
        object.__setattr__(self, "allowed_purposes", purposes)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "key_id": self.key_id,
            "key_digest": self.key_digest,
            "algorithm": self.algorithm.value,
            "status": self.status,
            "allowed_purposes": list(self.allowed_purposes),
        }

    @property
    def surface_digest(self) -> str:
        return content_digest(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> SignatureSurfaceV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "key_id",
                    "key_digest",
                    "algorithm",
                    "status",
                    "allowed_purposes",
                }
            ),
            field_name="signature surface",
        )
        try:
            algorithm = CryptoAlgorithmV1(
                _text(value.get("algorithm"), field_name="algorithm")
            )
        except ValueError as exc:
            raise PostQuantumReadinessError(
                "unknown current signature algorithm"
            ) from exc
        raw_purposes = value.get("allowed_purposes")
        if not isinstance(raw_purposes, list):
            raise PostQuantumReadinessError("allowed_purposes must be a list")
        return cls(
            schema=_text(value.get("schema"), field_name="schema"),
            key_id=_text(value.get("key_id"), field_name="key_id"),
            key_digest=_digest(value.get("key_digest"), field_name="key_digest"),
            algorithm=algorithm,
            status=_text(value.get("status"), field_name="status"),
            allowed_purposes=tuple(
                _text(item, field_name="allowed_purpose") for item in raw_purposes
            ),
        )


@dataclass(frozen=True, slots=True)
class PqcReadinessReportV1:
    case_id: str
    evaluated_at: int
    health_report_digest: str
    health_state: LongRangeHealthState
    current_trust_set_digest: str
    signature_surfaces: tuple[SignatureSurfaceV1, ...]
    migration_policy_digest: str
    state: PqcReadinessStateV1
    blockers: tuple[str, ...]
    post_quantum_support: bool = False
    schema: str = PQC_READINESS_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PQC_READINESS_REPORT_SCHEMA_V1:
            raise PostQuantumReadinessError(
                f"unsupported PQC readiness-report schema: {self.schema}"
            )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        object.__setattr__(
            self,
            "evaluated_at",
            _int(self.evaluated_at, field_name="evaluated_at"),
        )
        for name in (
            "health_report_digest",
            "current_trust_set_digest",
            "migration_policy_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        if not isinstance(self.health_state, LongRangeHealthState):
            raise PostQuantumReadinessError("unknown long-range health state")
        if not isinstance(self.state, PqcReadinessStateV1):
            raise PostQuantumReadinessError("unknown PQC readiness state")
        surfaces = tuple(
            sorted(self.signature_surfaces, key=lambda item: (item.key_id, item.key_digest))
        )
        if not surfaces:
            raise PostQuantumReadinessError("signature surface inventory cannot be empty")
        ids = [item.key_id for item in surfaces]
        if len(ids) != len(set(ids)):
            raise PostQuantumReadinessError("duplicate signature surface key_id")
        object.__setattr__(self, "signature_surfaces", surfaces)
        blockers = tuple(
            sorted({_text(item, field_name="blocker") for item in self.blockers})
        )
        if "pqc_adapter_not_implemented" not in blockers:
            raise PostQuantumReadinessError(
                "LRD-01F must preserve the missing-adapter blocker"
            )
        if self.health_state is LongRangeHealthState.HEALTHY:
            expected_state = PqcReadinessStateV1.ADAPTER_REQUIRED
            expected_health_blocker = False
        else:
            expected_state = PqcReadinessStateV1.BLOCKED_CURRENT_HEALTH
            expected_health_blocker = True
        if self.state is not expected_state:
            raise PostQuantumReadinessError(
                "PQC readiness state is inconsistent with current long-range health"
            )
        has_health_blocker = "current_long_range_health_not_healthy" in blockers
        if has_health_blocker != expected_health_blocker:
            raise PostQuantumReadinessError(
                "PQC readiness blockers are inconsistent with current health"
            )
        if self.post_quantum_support:
            raise PostQuantumReadinessError(
                "LRD-01F cannot claim post-quantum implementation support"
            )
        object.__setattr__(self, "blockers", blockers)

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "evaluated_at": self.evaluated_at,
            "health_report_digest": self.health_report_digest,
            "health_state": self.health_state.value,
            "current_trust_set_digest": self.current_trust_set_digest,
            "signature_surfaces": [
                item.canonical_dict() for item in self.signature_surfaces
            ],
            "migration_policy_digest": self.migration_policy_digest,
            "state": self.state.value,
            "blockers": list(self.blockers),
            "post_quantum_support": self.post_quantum_support,
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "report_digest": self.report_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PqcReadinessReportV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "case_id",
                    "evaluated_at",
                    "health_report_digest",
                    "health_state",
                    "current_trust_set_digest",
                    "signature_surfaces",
                    "migration_policy_digest",
                    "state",
                    "blockers",
                    "post_quantum_support",
                    "report_digest",
                }
            ),
            field_name="PQC readiness report",
        )
        raw_surfaces = value.get("signature_surfaces")
        if not isinstance(raw_surfaces, list):
            raise PostQuantumReadinessError("signature_surfaces must be a list")
        surfaces: list[SignatureSurfaceV1] = []
        for raw in raw_surfaces:
            if not isinstance(raw, Mapping):
                raise PostQuantumReadinessError("signature surface must be an object")
            surfaces.append(SignatureSurfaceV1.from_dict(raw))
        raw_blockers = value.get("blockers")
        if not isinstance(raw_blockers, list):
            raise PostQuantumReadinessError("blockers must be a list")
        try:
            health_state = LongRangeHealthState(
                _text(value.get("health_state"), field_name="health_state")
            )
            state = PqcReadinessStateV1(
                _text(value.get("state"), field_name="state")
            )
        except ValueError as exc:
            raise PostQuantumReadinessError(
                "unknown health or PQC readiness state"
            ) from exc
        support = value.get("post_quantum_support")
        if not isinstance(support, bool):
            raise PostQuantumReadinessError("post_quantum_support must be boolean")
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            evaluated_at=_int(value.get("evaluated_at"), field_name="evaluated_at"),
            health_report_digest=_digest(
                value.get("health_report_digest"),
                field_name="health_report_digest",
            ),
            health_state=health_state,
            current_trust_set_digest=_digest(
                value.get("current_trust_set_digest"),
                field_name="current_trust_set_digest",
            ),
            signature_surfaces=tuple(surfaces),
            migration_policy_digest=_digest(
                value.get("migration_policy_digest"),
                field_name="migration_policy_digest",
            ),
            state=state,
            blockers=tuple(
                _text(item, field_name="blocker") for item in raw_blockers
            ),
            post_quantum_support=support,
        )
        recorded = _digest(value.get("report_digest"), field_name="report_digest")
        if recorded != result.report_digest:
            raise PostQuantumReadinessError("PQC readiness report digest mismatch")
        return result


def build_pqc_readiness_report_v1(
    *,
    case_id: str,
    health_report: LongRangeHealthReportV1,
    current_trust_set: CryptoTrustSetV1,
    policy: PqcMigrationPolicyV1,
    evaluated_at: int,
) -> PqcReadinessReportV1:
    """Inventory current signature exposure without inventing PQC support."""

    normalized_case = _text(case_id, field_name="case_id")
    evaluated = _int(evaluated_at, field_name="evaluated_at")
    if health_report.case_id != normalized_case:
        raise PostQuantumReadinessError("long-range health case scope mismatch")
    if evaluated < health_report.evaluated_at:
        raise PostQuantumReadinessError(
            "PQC readiness assessment cannot predate current health evidence"
        )
    surfaces = tuple(
        SignatureSurfaceV1(
            key_id=key.key_id,
            key_digest=key.key_digest,
            algorithm=key.algorithm,
            status=key.status.value,
            allowed_purposes=tuple(item.value for item in key.allowed_purposes),
        )
        for key in current_trust_set.keys
    )
    blockers = ["pqc_adapter_not_implemented"]
    if health_report.state is LongRangeHealthState.HEALTHY:
        state = PqcReadinessStateV1.ADAPTER_REQUIRED
    else:
        state = PqcReadinessStateV1.BLOCKED_CURRENT_HEALTH
        blockers.append("current_long_range_health_not_healthy")
    return PqcReadinessReportV1(
        case_id=normalized_case,
        evaluated_at=evaluated,
        health_report_digest=health_report.report_digest,
        health_state=health_report.state,
        current_trust_set_digest=current_trust_set.trust_set_digest,
        signature_surfaces=surfaces,
        migration_policy_digest=policy.policy_digest,
        state=state,
        blockers=tuple(blockers),
    )


@dataclass(frozen=True, slots=True)
class ArchivalRenewalPlanV1:
    case_id: str
    readiness_report_digest: str
    health_report_digest: str
    classical_crypto_evidence_digest: str | None
    migration_policy_digest: str
    target_profile_digests: tuple[str, ...]
    state: ArchivalRenewalPlanStateV1
    preserve_original_evidence: bool = True
    additive_renewal_only: bool = True
    dual_verification_before_cutover: bool = True
    post_quantum_execution_authorized: bool = False
    schema: str = ARCHIVAL_RENEWAL_PLAN_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != ARCHIVAL_RENEWAL_PLAN_SCHEMA_V1:
            raise PostQuantumReadinessError(
                f"unsupported archival-renewal plan schema: {self.schema}"
            )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "readiness_report_digest",
            "health_report_digest",
            "migration_policy_digest",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), field_name=name),
            )
        object.__setattr__(
            self,
            "classical_crypto_evidence_digest",
            _optional_digest(
                self.classical_crypto_evidence_digest,
                field_name="classical_crypto_evidence_digest",
            ),
        )
        targets = tuple(
            sorted(
                {
                    _digest(item, field_name="target_profile_digest")
                    for item in self.target_profile_digests
                }
            )
        )
        if len(targets) != 2:
            raise PostQuantumReadinessError(
                "archival renewal plan requires both fixed PQC target families"
            )
        object.__setattr__(self, "target_profile_digests", targets)
        if not isinstance(self.state, ArchivalRenewalPlanStateV1):
            raise PostQuantumReadinessError("unknown archival-renewal plan state")
        for name in (
            "preserve_original_evidence",
            "additive_renewal_only",
            "dual_verification_before_cutover",
        ):
            if getattr(self, name) is not True:
                raise PostQuantumReadinessError(f"{name} must remain enabled")
        if self.post_quantum_execution_authorized:
            raise PostQuantumReadinessError(
                "LRD-01F cannot authorize post-quantum execution"
            )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "readiness_report_digest": self.readiness_report_digest,
            "health_report_digest": self.health_report_digest,
            "classical_crypto_evidence_digest": self.classical_crypto_evidence_digest,
            "migration_policy_digest": self.migration_policy_digest,
            "target_profile_digests": list(self.target_profile_digests),
            "state": self.state.value,
            "preserve_original_evidence": self.preserve_original_evidence,
            "additive_renewal_only": self.additive_renewal_only,
            "dual_verification_before_cutover": self.dual_verification_before_cutover,
            "post_quantum_execution_authorized": self.post_quantum_execution_authorized,
        }

    @property
    def plan_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "plan_digest": self.plan_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ArchivalRenewalPlanV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "case_id",
                    "readiness_report_digest",
                    "health_report_digest",
                    "classical_crypto_evidence_digest",
                    "migration_policy_digest",
                    "target_profile_digests",
                    "state",
                    "preserve_original_evidence",
                    "additive_renewal_only",
                    "dual_verification_before_cutover",
                    "post_quantum_execution_authorized",
                    "plan_digest",
                }
            ),
            field_name="archival renewal plan",
        )
        raw_targets = value.get("target_profile_digests")
        if not isinstance(raw_targets, list):
            raise PostQuantumReadinessError("target_profile_digests must be a list")
        try:
            state = ArchivalRenewalPlanStateV1(
                _text(value.get("state"), field_name="state")
            )
        except ValueError as exc:
            raise PostQuantumReadinessError(
                "unknown archival-renewal plan state"
            ) from exc
        bools: dict[str, bool] = {}
        for name in (
            "preserve_original_evidence",
            "additive_renewal_only",
            "dual_verification_before_cutover",
            "post_quantum_execution_authorized",
        ):
            raw = value.get(name)
            if not isinstance(raw, bool):
                raise PostQuantumReadinessError(f"{name} must be boolean")
            bools[name] = raw
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            readiness_report_digest=_digest(
                value.get("readiness_report_digest"),
                field_name="readiness_report_digest",
            ),
            health_report_digest=_digest(
                value.get("health_report_digest"),
                field_name="health_report_digest",
            ),
            classical_crypto_evidence_digest=_optional_digest(
                value.get("classical_crypto_evidence_digest"),
                field_name="classical_crypto_evidence_digest",
            ),
            migration_policy_digest=_digest(
                value.get("migration_policy_digest"),
                field_name="migration_policy_digest",
            ),
            target_profile_digests=tuple(
                _digest(item, field_name="target_profile_digest")
                for item in raw_targets
            ),
            state=state,
            preserve_original_evidence=bools["preserve_original_evidence"],
            additive_renewal_only=bools["additive_renewal_only"],
            dual_verification_before_cutover=bools[
                "dual_verification_before_cutover"
            ],
            post_quantum_execution_authorized=bools[
                "post_quantum_execution_authorized"
            ],
        )
        recorded = _digest(value.get("plan_digest"), field_name="plan_digest")
        if recorded != result.plan_digest:
            raise PostQuantumReadinessError("archival renewal plan digest mismatch")
        return result


def build_archival_renewal_plan_v1(
    *,
    health_report: LongRangeHealthReportV1,
    readiness_report: PqcReadinessReportV1,
    policy: PqcMigrationPolicyV1,
) -> ArchivalRenewalPlanV1:
    """Build an additive migration plan without executing or authorizing PQ signatures."""

    if readiness_report.case_id != health_report.case_id:
        raise PostQuantumReadinessError("archival renewal case scope mismatch")
    if readiness_report.health_report_digest != health_report.report_digest:
        raise PostQuantumReadinessError(
            "readiness report is bound to different long-range health evidence"
        )
    if readiness_report.migration_policy_digest != policy.policy_digest:
        raise PostQuantumReadinessError(
            "readiness report is bound to different PQC migration policy"
        )
    if readiness_report.state is PqcReadinessStateV1.ADAPTER_REQUIRED:
        state = ArchivalRenewalPlanStateV1.READY_FOR_ADAPTER_IMPLEMENTATION
    else:
        state = ArchivalRenewalPlanStateV1.BLOCKED_CURRENT_HEALTH
    return ArchivalRenewalPlanV1(
        case_id=health_report.case_id,
        readiness_report_digest=readiness_report.report_digest,
        health_report_digest=health_report.report_digest,
        classical_crypto_evidence_digest=health_report.crypto_evidence_digest,
        migration_policy_digest=policy.policy_digest,
        target_profile_digests=tuple(
            target.profile_digest for target in policy.targets
        ),
        state=state,
    )
