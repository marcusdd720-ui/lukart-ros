"""DR-02 recovery-continuity and storage-conformance evidence v1.

The Canonical Case Ledger remains the only writable Product history authority. This
module does not define a second backup format or persistence layer; it binds the
existing portable CaseLedgerBundle restore to explicit storage profiles and emits a
deterministic conformance artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from core.case_ledger.contracts import CaseId, CaseLedgerBundle, CaseLedgerContractError
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.durability import RecoveryIdentity, SQLiteProvenanceStore
from core.p3.contracts import content_digest, require_hex_digest

STORAGE_PROFILE_SCHEMA_V1 = "lukart.storage-profile.v1"
RECOVERY_DRILL_MANIFEST_SCHEMA_V1 = "lukart.recovery-drill-manifest.v1"
RECOVERY_CONFORMANCE_REPORT_SCHEMA_V1 = "lukart.recovery-conformance-report.v1"

_PROFILE_FIELDS = frozenset(
    {
        "schema",
        "backend_kind",
        "implementation_id",
        "implementation_version",
        "storage_schema",
        "configuration_digest",
        "profile_digest",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "case_id",
        "source_profile_digest",
        "target_profile_digest",
        "source_bundle_digest",
        "source_head_event_digest",
        "source_event_count",
        "source_backend_identity_digest",
        "manifest_digest",
    }
)
_REPORT_FIELDS = frozenset(
    {
        "schema",
        "manifest_digest",
        "target_backend_identity_digest",
        "restored_bundle_digest",
        "restored_head_event_digest",
        "restored_event_count",
        "state",
        "violations",
        "report_digest",
    }
)


class RecoveryContinuityV1Error(ValueError):
    """Fail-closed DR-02 contract violation."""


class RecoveryConformanceState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RecoveryContinuityV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _nonnegative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RecoveryContinuityV1Error(f"{field_name} must be a nonnegative integer")
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(
            _text(value, field_name=field_name), field_name=field_name
        )
    except ValueError as exc:
        raise RecoveryContinuityV1Error(str(exc)) from exc


def _optional_digest(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _digest(value, field_name=field_name)


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
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if unknown:
        details.append(f"unknown={unknown}")
    raise RecoveryContinuityV1Error(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


@dataclass(frozen=True, slots=True)
class StorageProfileV1:
    """Content-addressed, secret-free identity of one storage profile."""

    backend_kind: str
    implementation_id: str
    implementation_version: str
    storage_schema: str
    configuration_digest: str
    schema: str = STORAGE_PROFILE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != STORAGE_PROFILE_SCHEMA_V1:
            raise RecoveryContinuityV1Error(
                f"unsupported storage profile schema: {self.schema}"
            )
        object.__setattr__(
            self, "backend_kind", _text(self.backend_kind, field_name="backend_kind")
        )
        object.__setattr__(
            self,
            "implementation_id",
            _text(self.implementation_id, field_name="implementation_id"),
        )
        object.__setattr__(
            self,
            "implementation_version",
            _text(self.implementation_version, field_name="implementation_version"),
        )
        object.__setattr__(
            self,
            "storage_schema",
            _text(self.storage_schema, field_name="storage_schema"),
        )
        object.__setattr__(
            self,
            "configuration_digest",
            _digest(self.configuration_digest, field_name="configuration_digest"),
        )

    @classmethod
    def from_configuration(
        cls,
        *,
        backend_kind: str,
        implementation_id: str,
        implementation_version: str,
        storage_schema: str,
        public_configuration: Mapping[str, object],
    ) -> StorageProfileV1:
        """Build a profile from canonical non-secret configuration only."""

        return cls(
            backend_kind=backend_kind,
            implementation_id=implementation_id,
            implementation_version=implementation_version,
            storage_schema=storage_schema,
            configuration_digest=content_digest(dict(public_configuration)),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StorageProfileV1:
        _exact_keys(value, expected=_PROFILE_FIELDS, field_name="storage profile")
        profile = cls(
            backend_kind=_text(value.get("backend_kind"), field_name="backend_kind"),
            implementation_id=_text(
                value.get("implementation_id"), field_name="implementation_id"
            ),
            implementation_version=_text(
                value.get("implementation_version"), field_name="implementation_version"
            ),
            storage_schema=_text(
                value.get("storage_schema"), field_name="storage_schema"
            ),
            configuration_digest=_digest(
                value.get("configuration_digest"), field_name="configuration_digest"
            ),
            schema=_text(value.get("schema"), field_name="storage profile schema"),
        )
        recorded = _digest(value.get("profile_digest"), field_name="profile_digest")
        if recorded != profile.profile_digest:
            raise RecoveryContinuityV1Error("storage profile digest mismatch")
        return profile

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "backend_kind": self.backend_kind,
            "implementation_id": self.implementation_id,
            "implementation_version": self.implementation_version,
            "storage_schema": self.storage_schema,
            "configuration_digest": self.configuration_digest,
        }

    @property
    def profile_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "profile_digest": self.profile_digest}


@dataclass(frozen=True, slots=True)
class RecoveryDrillManifestV1:
    """Immutable declaration of the exact recovery continuity experiment."""

    case_id: str
    source_profile_digest: str
    target_profile_digest: str
    source_bundle_digest: str
    source_head_event_digest: str | None
    source_event_count: int
    source_backend_identity_digest: str
    schema: str = RECOVERY_DRILL_MANIFEST_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RECOVERY_DRILL_MANIFEST_SCHEMA_V1:
            raise RecoveryContinuityV1Error(
                f"unsupported recovery drill manifest schema: {self.schema}"
            )
        object.__setattr__(self, "case_id", _text(self.case_id, field_name="case_id"))
        for name in (
            "source_profile_digest",
            "target_profile_digest",
            "source_bundle_digest",
            "source_backend_identity_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "source_head_event_digest",
            _optional_digest(
                self.source_head_event_digest, field_name="source_head_event_digest"
            ),
        )
        object.__setattr__(
            self,
            "source_event_count",
            _nonnegative_int(self.source_event_count, field_name="source_event_count"),
        )
        if self.source_event_count == 0 and self.source_head_event_digest is not None:
            raise RecoveryContinuityV1Error("empty source cannot declare a head event")
        if self.source_event_count > 0 and self.source_head_event_digest is None:
            raise RecoveryContinuityV1Error("nonempty source requires a head event")

    @classmethod
    def build(
        cls,
        *,
        source_profile: StorageProfileV1,
        target_profile: StorageProfileV1,
        source_bundle: CaseLedgerBundle,
        source_backend_identity: RecoveryIdentity,
    ) -> RecoveryDrillManifestV1:
        head = source_bundle.head_event_id
        return cls(
            case_id=source_bundle.case_id.value,
            source_profile_digest=source_profile.profile_digest,
            target_profile_digest=target_profile.profile_digest,
            source_bundle_digest=source_bundle.bundle_digest.digest,
            source_head_event_digest=head.digest if head is not None else None,
            source_event_count=len(source_bundle.events),
            source_backend_identity_digest=source_backend_identity.digest(),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> RecoveryDrillManifestV1:
        _exact_keys(
            value, expected=_MANIFEST_FIELDS, field_name="recovery drill manifest"
        )
        manifest = cls(
            case_id=_text(value.get("case_id"), field_name="case_id"),
            source_profile_digest=_digest(
                value.get("source_profile_digest"), field_name="source_profile_digest"
            ),
            target_profile_digest=_digest(
                value.get("target_profile_digest"), field_name="target_profile_digest"
            ),
            source_bundle_digest=_digest(
                value.get("source_bundle_digest"), field_name="source_bundle_digest"
            ),
            source_head_event_digest=_optional_digest(
                value.get("source_head_event_digest"),
                field_name="source_head_event_digest",
            ),
            source_event_count=_nonnegative_int(
                value.get("source_event_count"), field_name="source_event_count"
            ),
            source_backend_identity_digest=_digest(
                value.get("source_backend_identity_digest"),
                field_name="source_backend_identity_digest",
            ),
            schema=_text(value.get("schema"), field_name="manifest schema"),
        )
        recorded = _digest(value.get("manifest_digest"), field_name="manifest_digest")
        if recorded != manifest.manifest_digest:
            raise RecoveryContinuityV1Error("recovery drill manifest digest mismatch")
        return manifest

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "source_profile_digest": self.source_profile_digest,
            "target_profile_digest": self.target_profile_digest,
            "source_bundle_digest": self.source_bundle_digest,
            "source_head_event_digest": self.source_head_event_digest,
            "source_event_count": self.source_event_count,
            "source_backend_identity_digest": self.source_backend_identity_digest,
        }

    @property
    def manifest_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "manifest_digest": self.manifest_digest}


@dataclass(frozen=True, slots=True)
class RecoveryConformanceReportV1:
    """Deterministic result; PASS never grants Product or release authority."""

    manifest_digest: str
    target_backend_identity_digest: str
    restored_bundle_digest: str
    restored_head_event_digest: str | None
    restored_event_count: int
    state: RecoveryConformanceState
    violations: tuple[str, ...] = ()
    schema: str = RECOVERY_CONFORMANCE_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RECOVERY_CONFORMANCE_REPORT_SCHEMA_V1:
            raise RecoveryContinuityV1Error(
                f"unsupported recovery report schema: {self.schema}"
            )
        for name in (
            "manifest_digest",
            "target_backend_identity_digest",
            "restored_bundle_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "restored_head_event_digest",
            _optional_digest(
                self.restored_head_event_digest, field_name="restored_head_event_digest"
            ),
        )
        object.__setattr__(
            self,
            "restored_event_count",
            _nonnegative_int(self.restored_event_count, field_name="restored_event_count"),
        )
        if not isinstance(self.state, RecoveryConformanceState):
            raise RecoveryContinuityV1Error("unknown recovery conformance state")
        normalized = tuple(
            sorted({_text(item, field_name="violation") for item in self.violations})
        )
        object.__setattr__(self, "violations", normalized)
        if self.state is RecoveryConformanceState.PASS and normalized:
            raise RecoveryContinuityV1Error("PASS report cannot contain violations")
        if self.state is RecoveryConformanceState.FAIL and not normalized:
            raise RecoveryContinuityV1Error("FAIL report requires violations")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> RecoveryConformanceReportV1:
        _exact_keys(
            value, expected=_REPORT_FIELDS, field_name="recovery conformance report"
        )
        raw_violations = value.get("violations")
        if not isinstance(raw_violations, list):
            raise RecoveryContinuityV1Error("violations must be a list")
        try:
            state = RecoveryConformanceState(
                _text(value.get("state"), field_name="recovery state")
            )
        except ValueError as exc:
            raise RecoveryContinuityV1Error(
                "unknown recovery conformance state"
            ) from exc
        report = cls(
            manifest_digest=_digest(
                value.get("manifest_digest"), field_name="manifest_digest"
            ),
            target_backend_identity_digest=_digest(
                value.get("target_backend_identity_digest"),
                field_name="target_backend_identity_digest",
            ),
            restored_bundle_digest=_digest(
                value.get("restored_bundle_digest"), field_name="restored_bundle_digest"
            ),
            restored_head_event_digest=_optional_digest(
                value.get("restored_head_event_digest"),
                field_name="restored_head_event_digest",
            ),
            restored_event_count=_nonnegative_int(
                value.get("restored_event_count"), field_name="restored_event_count"
            ),
            state=state,
            violations=tuple(
                _text(item, field_name="violation") for item in raw_violations
            ),
            schema=_text(value.get("schema"), field_name="report schema"),
        )
        recorded = _digest(value.get("report_digest"), field_name="report_digest")
        if recorded != report.report_digest:
            raise RecoveryContinuityV1Error("recovery conformance report digest mismatch")
        return report

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "manifest_digest": self.manifest_digest,
            "target_backend_identity_digest": self.target_backend_identity_digest,
            "restored_bundle_digest": self.restored_bundle_digest,
            "restored_head_event_digest": self.restored_head_event_digest,
            "restored_event_count": self.restored_event_count,
            "state": self.state.value,
            "violations": list(self.violations),
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "report_digest": self.report_digest}


def evaluate_recovery_conformance(
    *,
    manifest: RecoveryDrillManifestV1,
    restored_bundle: CaseLedgerBundle,
    target_backend_identity: RecoveryIdentity,
) -> RecoveryConformanceReportV1:
    """Compare restored Product identity with the declared experiment."""

    violations: list[str] = []
    if restored_bundle.case_id.value != manifest.case_id:
        violations.append("case_id_mismatch")
    if restored_bundle.bundle_digest.digest != manifest.source_bundle_digest:
        violations.append("bundle_digest_mismatch")
    head = restored_bundle.head_event_id
    restored_head = head.digest if head is not None else None
    if restored_head != manifest.source_head_event_digest:
        violations.append("head_event_mismatch")
    if len(restored_bundle.events) != manifest.source_event_count:
        violations.append("event_count_mismatch")
    return RecoveryConformanceReportV1(
        manifest_digest=manifest.manifest_digest,
        target_backend_identity_digest=target_backend_identity.digest(),
        restored_bundle_digest=restored_bundle.bundle_digest.digest,
        restored_head_event_digest=restored_head,
        restored_event_count=len(restored_bundle.events),
        state=(
            RecoveryConformanceState.PASS
            if not violations
            else RecoveryConformanceState.FAIL
        ),
        violations=tuple(violations),
    )


def run_sqlite_case_recovery_drill(
    *,
    source_path: str | Path,
    target_path: str | Path,
    case_id: CaseId,
    source_profile: StorageProfileV1,
    target_profile: StorageProfileV1,
    max_events: int = 10_000,
) -> tuple[RecoveryDrillManifestV1, RecoveryConformanceReportV1]:
    """Exercise the real CCL restore boundary and emit deterministic DR-02 evidence.

    The function intentionally supports only the existing SQLite provenance backend.
    A future backend must receive its own tested adapter rather than being implied by
    a generic profile string.
    """

    if source_profile.backend_kind != "sqlite-provenance":
        raise RecoveryContinuityV1Error(
            "unsupported source backend for sqlite recovery drill"
        )
    if target_profile.backend_kind != "sqlite-provenance":
        raise RecoveryContinuityV1Error(
            "unsupported target backend for sqlite recovery drill"
        )

    source_file = Path(source_path)
    target_file = Path(target_path)
    with CanonicalCaseLedger(source_file) as source_ledger:
        source_bundle = source_ledger.export_case(case_id, max_events=max_events)
    with SQLiteProvenanceStore(source_file) as source_store:
        source_backend_identity = source_store.state_identity()

    manifest = RecoveryDrillManifestV1.build(
        source_profile=source_profile,
        target_profile=target_profile,
        source_bundle=source_bundle,
        source_backend_identity=source_backend_identity,
    )

    try:
        with CanonicalCaseLedger(target_file) as target_ledger:
            restored = target_ledger.restore_case(
                case_id,
                cast(Mapping[str, object], source_bundle.canonical_dict()),
                max_events=max_events,
            )
    except CaseLedgerContractError as exc:
        raise RecoveryContinuityV1Error(
            "canonical recovery drill restore refused"
        ) from exc

    with SQLiteProvenanceStore(target_file) as target_store:
        target_identity = target_store.state_identity()
    report = evaluate_recovery_conformance(
        manifest=manifest,
        restored_bundle=restored,
        target_backend_identity=target_identity,
    )
    if report.state is not RecoveryConformanceState.PASS:
        raise RecoveryContinuityV1Error(
            "canonical recovery drill completed with identity mismatch"
        )
    return manifest, report
