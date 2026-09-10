"""CASE-OPS-08 derivation compatibility and migration-readiness inventory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from core.private_case_runtime_bridge_v1 import (
    PrivateCaseRuntimeBridgeError,
    load_verified_projection,
)
from core.private_evidence_derivation_v1 import (
    MAX_TEXT_INPUT_BYTES,
    UTF8_TEXT_TRANSFORM,
    UTF8_TEXT_TRANSFORM_VERSION,
    ReplayClass,
    load_derivation,
)
from core.private_evidence_v1 import (
    PrivateEvidenceError,
    PrivateEvidenceStore,
    canonical_json,
    digest_object,
)
from core.private_ocr_replay_v1 import (
    OCR_CONFIG_V1,
    OCR_TRANSFORM_ID_V1,
    OCR_TRANSFORM_VERSION_V1,
)

SCHEMA_MIGRATION_READINESS_REPORT_V1 = "lukart.private-derivation-migration-readiness.v1"
MIGRATION_POLICY_SCHEMA_V1 = "lukart.private-derivation-migration-policy.v1"


class ConfigResolution(StrEnum):
    KNOWN = "KNOWN"
    RECOVERED_FROM_VERIFIED_CANDIDATE = "RECOVERED_FROM_VERIFIED_CANDIDATE"
    UNRESOLVED = "UNRESOLVED"


class CompatibilityStatus(StrEnum):
    CURRENT_DETERMINISTIC = "CURRENT_DETERMINISTIC"
    REPLAY_READY_ENVIRONMENT_BOUND = "REPLAY_READY_ENVIRONMENT_BOUND"
    CONFIG_RECOVERY_REQUIRED = "CONFIG_RECOVERY_REQUIRED"
    EXPLICIT_MIGRATION_REQUIRED = "EXPLICIT_MIGRATION_REQUIRED"


class MigrationAction(StrEnum):
    NONE = "NONE"
    SUPPLY_VERIFIED_CONFIG = "SUPPLY_VERIFIED_CONFIG"
    DEFINE_VERSIONED_MIGRATION = "DEFINE_VERSIONED_MIGRATION"


@dataclass(frozen=True, slots=True)
class DerivationMigrationEntryV1:
    derivation_receipt_digest: str
    semantic_derivation_id: str
    source_evidence_id: str
    derived_evidence_id: str
    replay_class: str
    transform_id: str
    transform_version: int
    config_digest: str
    config_resolution: str
    compatibility_status: str
    migration_action: str
    resolved_config: dict[str, object] | None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PrivateDerivationMigrationReadinessV1:
    schema: str
    case_scope_digest: str
    projection_id: str
    policy_id: str
    overall_status: str
    entries: tuple[DerivationMigrationEntryV1, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_scope_digest": self.case_scope_digest,
            "projection_id": self.projection_id,
            "policy_id": self.policy_id,
            "overall_status": self.overall_status,
            "entries": [entry.canonical_dict() for entry in self.entries],
        }

    @property
    def report_id(self) -> str:
        return digest_object(self.canonical_dict())


_UTF8_CONFIG_FIELDS = frozenset({"encoding", "newline", "bom", "nul", "max_input_bytes"})
_DEFAULT_UTF8_CONFIG: dict[str, object] = {
    "encoding": "utf-8-strict",
    "newline": "LF",
    "bom": "reject",
    "nul": "reject",
    "max_input_bytes": MAX_TEXT_INPUT_BYTES,
}
_MIGRATION_POLICY_V1: dict[str, object] = {
    "schema": MIGRATION_POLICY_SCHEMA_V1,
    "supported_profiles": [
        {
            "transform_id": UTF8_TEXT_TRANSFORM,
            "transform_version": UTF8_TEXT_TRANSFORM_VERSION,
            "replay_class": ReplayClass.DETERMINISTIC.value,
            "config_contract": {
                "fields": sorted(_UTF8_CONFIG_FIELDS),
                "max_input_bytes_min": 1,
                "max_input_bytes_max": MAX_TEXT_INPUT_BYTES,
            },
        },
        {
            "transform_id": OCR_TRANSFORM_ID_V1,
            "transform_version": OCR_TRANSFORM_VERSION_V1,
            "replay_class": ReplayClass.ENVIRONMENT_BOUND.value,
            "config": OCR_CONFIG_V1,
        },
    ],
    "historical_receipts_mutated": False,
    "unknown_profile_action": MigrationAction.DEFINE_VERSIONED_MIGRATION.value,
}
MIGRATION_POLICY_ID_V1 = digest_object(_MIGRATION_POLICY_V1)


def _load_mapping(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateEvidenceError(f"{label} missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceError(f"{label} must be a mapping")
    return value


def _valid_utf8_config(candidate: dict[str, object]) -> bool:
    if set(candidate) != _UTF8_CONFIG_FIELDS:
        return False
    max_input = candidate.get("max_input_bytes")
    if isinstance(max_input, bool) or not isinstance(max_input, int):
        return False
    if max_input < 1 or max_input > MAX_TEXT_INPUT_BYTES:
        return False
    return (
        candidate.get("encoding") == "utf-8-strict"
        and candidate.get("newline") == "LF"
        and candidate.get("bom") == "reject"
        and candidate.get("nul") == "reject"
    )


def _utf8_resolution(
    receipt_digest: str,
    config_digest: str,
    candidates: dict[str, dict[str, object]],
) -> tuple[ConfigResolution, dict[str, object] | None, CompatibilityStatus, MigrationAction]:
    if digest_object(_DEFAULT_UTF8_CONFIG) == config_digest:
        if receipt_digest in candidates and candidates[receipt_digest] != _DEFAULT_UTF8_CONFIG:
            raise PrivateEvidenceError("operator config candidate contradicts known UTF-8 profile")
        return (
            ConfigResolution.KNOWN,
            dict(_DEFAULT_UTF8_CONFIG),
            CompatibilityStatus.CURRENT_DETERMINISTIC,
            MigrationAction.NONE,
        )

    candidate = candidates.get(receipt_digest)
    if candidate is None:
        return (
            ConfigResolution.UNRESOLVED,
            None,
            CompatibilityStatus.CONFIG_RECOVERY_REQUIRED,
            MigrationAction.SUPPLY_VERIFIED_CONFIG,
        )
    if not _valid_utf8_config(candidate):
        raise PrivateEvidenceError("operator config candidate violates UTF-8 v1 config contract")
    if digest_object(candidate) != config_digest:
        raise PrivateEvidenceError("operator config candidate digest mismatch")
    return (
        ConfigResolution.RECOVERED_FROM_VERIFIED_CANDIDATE,
        dict(candidate),
        CompatibilityStatus.CURRENT_DETERMINISTIC,
        MigrationAction.NONE,
    )


def build_derivation_migration_readiness(
    store: PrivateEvidenceStore,
    *,
    config_candidates: dict[str, dict[str, object]] | None = None,
) -> PrivateDerivationMigrationReadinessV1:
    """Verify runtime-supported derivations and classify future migration work without mutation."""
    candidates = dict(config_candidates or {})
    try:
        projection = load_verified_projection(store)
    except PrivateCaseRuntimeBridgeError as exc:
        raise PrivateEvidenceError("cannot inventory an invalid runtime projection") from exc

    known_receipts = {item.derivation_receipt_digest for item in projection.documents}
    unknown_candidates = set(candidates) - known_receipts
    if unknown_candidates:
        raise PrivateEvidenceError("operator config candidate references an unknown derivation")

    entries: list[DerivationMigrationEntryV1] = []
    for document in projection.documents:
        result = load_derivation(store, document.derivation_receipt_digest)
        receipt = _load_mapping(result.derivation_receipt_path, label="derivation receipt")
        if digest_object(receipt) != document.derivation_receipt_digest:
            raise PrivateEvidenceError("derivation receipt changed during migration inventory")

        transform_id = receipt.get("transform_id")
        transform_version = receipt.get("transform_version")
        config_digest = receipt.get("config_digest")
        replay_class = receipt.get("replay_class")
        if not isinstance(transform_id, str) or not transform_id:
            raise PrivateEvidenceError("invalid derivation transform id")
        if isinstance(transform_version, bool) or not isinstance(transform_version, int):
            raise PrivateEvidenceError("invalid derivation transform version")
        if not isinstance(config_digest, str) or not isinstance(replay_class, str):
            raise PrivateEvidenceError("invalid derivation migration identity")

        resolution = ConfigResolution.UNRESOLVED
        resolved_config: dict[str, object] | None = None
        compatibility = CompatibilityStatus.EXPLICIT_MIGRATION_REQUIRED
        action = MigrationAction.DEFINE_VERSIONED_MIGRATION

        if (
            transform_id == UTF8_TEXT_TRANSFORM
            and transform_version == UTF8_TEXT_TRANSFORM_VERSION
            and replay_class == ReplayClass.DETERMINISTIC.value
        ):
            resolution, resolved_config, compatibility, action = _utf8_resolution(
                document.derivation_receipt_digest,
                config_digest,
                candidates,
            )
        elif (
            transform_id == OCR_TRANSFORM_ID_V1
            and transform_version == OCR_TRANSFORM_VERSION_V1
            and replay_class == ReplayClass.ENVIRONMENT_BOUND.value
            and config_digest == digest_object(OCR_CONFIG_V1)
        ):
            if document.derivation_receipt_digest in candidates:
                raise PrivateEvidenceError(
                    "operator config candidate is not accepted for known OCR v1"
                )
            resolution = ConfigResolution.KNOWN
            resolved_config = dict(OCR_CONFIG_V1)
            compatibility = CompatibilityStatus.REPLAY_READY_ENVIRONMENT_BOUND
            action = MigrationAction.NONE
        elif document.derivation_receipt_digest in candidates:
            raise PrivateEvidenceError(
                "operator config candidate cannot authorize an unknown profile"
            )

        entries.append(
            DerivationMigrationEntryV1(
                derivation_receipt_digest=document.derivation_receipt_digest,
                semantic_derivation_id=document.derivation_identity,
                source_evidence_id=document.evidence_id,
                derived_evidence_id=document.derived_evidence_id,
                replay_class=replay_class,
                transform_id=transform_id,
                transform_version=transform_version,
                config_digest=config_digest,
                config_resolution=resolution.value,
                compatibility_status=compatibility.value,
                migration_action=action.value,
                resolved_config=resolved_config,
            )
        )

    entries.sort(key=lambda item: item.derivation_receipt_digest)
    overall = (
        "READY"
        if all(item.migration_action == MigrationAction.NONE.value for item in entries)
        else "ACTION_REQUIRED"
    )
    return PrivateDerivationMigrationReadinessV1(
        schema=SCHEMA_MIGRATION_READINESS_REPORT_V1,
        case_scope_digest=store.case_scope_digest,
        projection_id=projection.projection_id,
        policy_id=MIGRATION_POLICY_ID_V1,
        overall_status=overall,
        entries=tuple(entries),
    )


def write_migration_readiness_report(
    report: PrivateDerivationMigrationReadinessV1,
    target: Path,
    *,
    repo_root: Path,
) -> Path:
    """Write immutable private operator evidence outside the public repository."""
    absolute = Path(os.path.abspath(target.expanduser()))
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and candidate.is_symlink():
            raise PrivateEvidenceError("migration report path must not traverse symlinks")
    resolved_repo = repo_root.resolve()
    resolved_target = absolute.resolve()
    if resolved_target == resolved_repo or resolved_repo in resolved_target.parents:
        raise PrivateEvidenceError("migration report must be outside the public repository")

    payload = canonical_json(report.canonical_dict()) + b"\n"
    resolved_target.parent.mkdir(parents=True, exist_ok=True)
    if resolved_target.parent.is_symlink():
        raise PrivateEvidenceError("migration report parent must not be a symlink")
    try:
        fd = os.open(resolved_target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if resolved_target.is_symlink() or resolved_target.read_bytes() != payload:
            raise PrivateEvidenceError("immutable migration report divergence detected") from None
        return resolved_target
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        resolved_target.unlink(missing_ok=True)
        raise
    return resolved_target
