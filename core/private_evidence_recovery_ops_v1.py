"""Operator recovery and custody evidence for CASE-OPS-05.

CASE-OPS-05 composes CASE-OPS-03/04. It does not introduce another evidence
store or case-history authority. Machine-verifiable recovery evidence is kept
separate from operator assertions about physical/offline conditions.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext
from core.local_case_store import PrivacyViolation, validate_untrusted_path
from core.private_evidence_recovery_set_v1 import (
    RECOVERY_MEMBER_COUNT,
    RecoveryDrillReceiptV1,
    RecoverySetResultV1,
    RecoverySetV1,
    create_redundant_recovery_set,
    restore_recovery_set_member,
    run_recovery_set_drill,
)
from core.private_evidence_recovery_v1 import RECOVERY_SUFFIX
from core.private_evidence_v1 import canonical_json, digest_object

SCHEMA_OPERATOR_DRILL_EVIDENCE = "lukart.private-evidence-operator-drill.v1"
SCHEMA_RECOVERY_ROTATION_RECEIPT = "lukart.private-evidence-recovery-rotation.v1"
OPERATOR_ASSERTION_CLASS = "OPERATOR_ASSERTED_NOT_INDEPENDENTLY_VERIFIED"
OPERATOR_RECOVERY_PROFILE = "LOCAL_REDUNDANT_RECOVERY_OPERATOR_V1"
RECOVERY_SET_RECORD_SUFFIX = ".mvros-recovery-set.json"
RECOVERY_DRILL_RECORD_SUFFIX = ".mvros-recovery-drill.json"
RECOVERY_ROTATION_RECORD_SUFFIX = ".mvros-recovery-rotation.json"


class PrivateEvidenceRecoveryOpsError(RuntimeError):
    """Fail-closed error at the CASE-OPS-05 operator boundary."""


@dataclass(frozen=True, slots=True)
class RecoveryOperatorAssertionsV1:
    """Explicit human assertions that repository code cannot independently prove."""

    source_workstation_unavailable: bool
    network_disconnected: bool
    media_physically_separate: bool
    recovery_secrets_separately_custodied: bool

    @property
    def complete(self) -> bool:
        return all(
            (
                self.source_workstation_unavailable,
                self.network_disconnected,
                self.media_physically_separate,
                self.recovery_secrets_separately_custodied,
            )
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "source_workstation_unavailable": self.source_workstation_unavailable,
            "network_disconnected": self.network_disconnected,
            "media_physically_separate": self.media_physically_separate,
            "recovery_secrets_separately_custodied": (
                self.recovery_secrets_separately_custodied
            ),
        }


@dataclass(frozen=True, slots=True)
class RecoveryOperatorDrillEvidenceV1:
    schema: str
    profile: str
    assertion_class: str
    observed_at: str
    operator_subject_digest: str
    machine_receipt: RecoveryDrillReceiptV1
    assertions: RecoveryOperatorAssertionsV1
    status: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile": self.profile,
            "assertion_class": self.assertion_class,
            "observed_at": self.observed_at,
            "operator_subject_digest": self.operator_subject_digest,
            "machine_receipt": self.machine_receipt.canonical_dict(),
            "assertions": self.assertions.canonical_dict(),
            "status": self.status,
        }

    @property
    def evidence_id(self) -> str:
        return digest_object(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class RecoveryRotationReceiptV1:
    schema: str
    profile: str
    rotated_at: str
    old_recovery_set_id: str
    source_member_slot: str
    source_capsule_id: str
    new_recovery_set_id: str
    snapshot_digest: str
    key_identity_digest: str
    result: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile": self.profile,
            "rotated_at": self.rotated_at,
            "old_recovery_set_id": self.old_recovery_set_id,
            "source_member_slot": self.source_member_slot,
            "source_capsule_id": self.source_capsule_id,
            "new_recovery_set_id": self.new_recovery_set_id,
            "snapshot_digest": self.snapshot_digest,
            "key_identity_digest": self.key_identity_digest,
            "result": self.result,
        }

    @property
    def receipt_id(self) -> str:
        return digest_object(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class RecoveryRotationResultV1:
    recovery_set_result: RecoverySetResultV1
    receipt: RecoveryRotationReceiptV1


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_existing_path(path: Path, *, label: str) -> Path:
    try:
        candidate = validate_untrusted_path(path, label=label)
    except PrivacyViolation as exc:
        raise PrivateEvidenceRecoveryOpsError(str(exc)) from exc
    return candidate.resolve()


def _safe_existing_dir(path: Path, *, label: str) -> Path:
    candidate = _safe_existing_path(path, label=label)
    if not candidate.is_dir():
        raise PrivateEvidenceRecoveryOpsError(f"{label} must be an existing directory")
    return candidate


def _outside_repo(path: Path, repo_root: Path | None, *, label: str) -> None:
    if repo_root is None:
        return
    root = _safe_existing_dir(repo_root, label="repository root")
    candidate = path.resolve()
    if candidate == root or root in candidate.parents:
        raise PrivateEvidenceRecoveryOpsError(f"{label} must be outside the public repository")


def _safe_output(path: Path, *, repo_root: Path | None, label: str) -> Path:
    raw = Path(os.path.abspath(path.expanduser()))
    parent = _safe_existing_dir(raw.parent, label=f"{label} parent")
    target = parent / raw.name
    _outside_repo(target, repo_root, label=label)
    if target.exists() or target.is_symlink():
        raise PrivateEvidenceRecoveryOpsError(f"{label} already exists")
    return target


def _write_record(
    path: Path,
    value: dict[str, object],
    *,
    repo_root: Path | None,
    label: str,
) -> Path:
    target = _safe_output(path, repo_root=repo_root, label=label)
    payload = canonical_json(value) + b"\n"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def _read_canonical_mapping(path: Path, *, label: str) -> dict[str, object]:
    source = _safe_existing_path(path, label=label)
    if source.is_symlink() or not source.is_file():
        raise PrivateEvidenceRecoveryOpsError(f"{label} must be a regular file")
    try:
        raw = source.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceRecoveryOpsError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceRecoveryOpsError(f"{label} must contain a JSON mapping")
    mapping = dict(value)
    if raw != canonical_json(mapping) + b"\n":
        raise PrivateEvidenceRecoveryOpsError(f"{label} is not canonical JSON")
    return mapping


def recovery_set_record_path(member_path: Path) -> Path:
    """Return the digest-only sidecar path adjacent to a CASE-OPS-04 member."""
    member = Path(os.path.abspath(member_path.expanduser()))
    if not member.name.endswith(RECOVERY_SUFFIX):
        raise PrivateEvidenceRecoveryOpsError(
            f"recovery member must end with {RECOVERY_SUFFIX}"
        )
    stem = member.name[: -len(RECOVERY_SUFFIX)]
    return member.parent / f"{stem}{RECOVERY_SET_RECORD_SUFFIX}"


def write_recovery_set_record(
    recovery_set: RecoverySetV1,
    path: Path,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Persist one strict canonical digest-only recovery-set record."""
    parsed = RecoverySetV1.from_dict(recovery_set.canonical_dict())
    return _write_record(
        path,
        parsed.canonical_dict(),
        repo_root=repo_root,
        label="recovery-set record",
    )


def write_redundant_recovery_set_records(
    recovery_set: RecoverySetV1,
    member_paths: tuple[Path, Path],
    *,
    repo_root: Path | None = None,
) -> tuple[Path, Path]:
    """Write identical set records beside both members; roll back partial sidecars."""
    targets = tuple(recovery_set_record_path(path) for path in member_paths)
    written: list[Path] = []
    try:
        for target in targets:
            written.append(
                write_recovery_set_record(recovery_set, target, repo_root=repo_root)
            )
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return targets[0], targets[1]


def load_recovery_set_record(path: Path) -> RecoverySetV1:
    """Load and strictly validate one canonical digest-only recovery-set record."""
    mapping = _read_canonical_mapping(path, label="recovery-set record")
    try:
        parsed = RecoverySetV1.from_dict(mapping)
    except RuntimeError as exc:
        raise PrivateEvidenceRecoveryOpsError("recovery-set record is invalid") from exc
    if canonical_json(mapping) != canonical_json(parsed.canonical_dict()):
        raise PrivateEvidenceRecoveryOpsError("recovery-set record changed during parsing")
    return parsed


def run_operator_recovery_drill(
    recovery_set: RecoverySetV1,
    member_paths: tuple[Path, Path],
    restore_targets: tuple[Path, Path],
    *,
    passphrases: tuple[str, str],
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    assertions: RecoveryOperatorAssertionsV1,
    repo_root: Path | None = None,
) -> RecoveryOperatorDrillEvidenceV1:
    """Run the machine drill and bind explicit, non-independent operator assertions."""
    machine_receipt = run_recovery_set_drill(
        recovery_set,
        member_paths,
        restore_targets,
        passphrases=passphrases,
        authorization=authorization,
        tenant_id=tenant_id,
        case_id=case_id,
        repo_root=repo_root,
    )
    status = (
        "OPERATOR_ATTESTED_MACHINE_PASS"
        if assertions.complete
        else "INCOMPLETE_OPERATOR_ASSERTIONS"
    )
    return RecoveryOperatorDrillEvidenceV1(
        schema=SCHEMA_OPERATOR_DRILL_EVIDENCE,
        profile=OPERATOR_RECOVERY_PROFILE,
        assertion_class=OPERATOR_ASSERTION_CLASS,
        observed_at=_timestamp(),
        operator_subject_digest=digest_object(
            {"subject_id": authorization.subject_id.strip()}
        ),
        machine_receipt=machine_receipt,
        assertions=assertions,
        status=status,
    )


def write_operator_drill_evidence(
    evidence: RecoveryOperatorDrillEvidenceV1,
    path: Path,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Persist a canonical receipt containing no paths, passphrases, or raw keys."""
    return _write_record(
        path,
        evidence.canonical_dict(),
        repo_root=repo_root,
        label="operator recovery-drill evidence",
    )


def rotate_recovery_set_secrets(
    recovery_set: RecoverySetV1,
    *,
    source_slot: str,
    source_capsule: Path,
    old_passphrase: str,
    staging_parent: Path,
    new_destinations: tuple[Path, Path],
    new_passphrases: tuple[str, str],
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> RecoveryRotationResultV1:
    """Issue a fresh 1-of-2 set from one surviving member without rewriting history."""
    parsed = RecoverySetV1.from_dict(recovery_set.canonical_dict())
    member = next((item for item in parsed.members if item.slot == source_slot), None)
    if member is None:
        raise PrivateEvidenceRecoveryOpsError("unknown recovery source member slot")
    if old_passphrase in new_passphrases:
        raise PrivateEvidenceRecoveryOpsError(
            "new recovery passphrases must not reuse the surviving old passphrase"
        )
    parent = _safe_existing_dir(staging_parent, label="recovery rotation staging parent")
    _outside_repo(parent, repo_root, label="recovery rotation staging parent")
    stage = parent / f".mvros-recovery-rotation-{secrets.token_hex(8)}"
    created_paths: tuple[Path, Path] | None = None
    try:
        restored = restore_recovery_set_member(
            parsed,
            slot=source_slot,
            capsule_path=source_capsule,
            passphrase=old_passphrase,
            destination=stage,
            authorization=authorization,
            tenant_id=tenant_id,
            case_id=case_id,
            repo_root=repo_root,
        )
        rotated = create_redundant_recovery_set(
            restored.store,
            new_destinations,
            passphrases=new_passphrases,
            repo_root=repo_root,
        )
        created_paths = rotated.member_paths
        if rotated.recovery_set.snapshot_digest != parsed.snapshot_digest:
            raise PrivateEvidenceRecoveryOpsError(
                "recovery secret rotation changed the encrypted evidence snapshot"
            )
        if rotated.recovery_set.recovery_set_id == parsed.recovery_set_id:
            raise PrivateEvidenceRecoveryOpsError(
                "recovery secret rotation did not issue a fresh recovery-set identity"
            )
        key_identity_digest = digest_object(
            {
                "identities": [
                    {"key_id": key_id, "key_version": key_version}
                    for key_id, key_version in restored.key_provider.identities
                ]
            }
        )
        receipt = RecoveryRotationReceiptV1(
            schema=SCHEMA_RECOVERY_ROTATION_RECEIPT,
            profile=OPERATOR_RECOVERY_PROFILE,
            rotated_at=_timestamp(),
            old_recovery_set_id=parsed.recovery_set_id,
            source_member_slot=member.slot,
            source_capsule_id=member.capsule_id,
            new_recovery_set_id=rotated.recovery_set.recovery_set_id,
            snapshot_digest=parsed.snapshot_digest,
            key_identity_digest=key_identity_digest,
            result="PASS",
        )
        return RecoveryRotationResultV1(
            recovery_set_result=rotated,
            receipt=receipt,
        )
    except Exception:
        if created_paths is not None:
            for path in created_paths:
                shutil.rmtree(path, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def write_rotation_receipt(
    receipt: RecoveryRotationReceiptV1,
    path: Path,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Persist digest-only rotation lineage; old recovery members remain immutable."""
    return _write_record(
        path,
        receipt.canonical_dict(),
        repo_root=repo_root,
        label="recovery rotation receipt",
    )


def validate_operator_evidence_shape(
    evidence: RecoveryOperatorDrillEvidenceV1,
) -> None:
    """Fail closed if an in-memory operator evidence object has impossible semantics."""
    if evidence.schema != SCHEMA_OPERATOR_DRILL_EVIDENCE:
        raise PrivateEvidenceRecoveryOpsError("unsupported operator drill evidence schema")
    if evidence.profile != OPERATOR_RECOVERY_PROFILE:
        raise PrivateEvidenceRecoveryOpsError("unsupported operator recovery profile")
    if evidence.assertion_class != OPERATOR_ASSERTION_CLASS:
        raise PrivateEvidenceRecoveryOpsError("unsupported operator assertion class")
    if evidence.machine_receipt.result != "PASS":
        raise PrivateEvidenceRecoveryOpsError("machine recovery drill is not PASS")
    expected = (
        "OPERATOR_ATTESTED_MACHINE_PASS"
        if evidence.assertions.complete
        else "INCOMPLETE_OPERATOR_ASSERTIONS"
    )
    if evidence.status != expected:
        raise PrivateEvidenceRecoveryOpsError("operator drill evidence status is inconsistent")
    if evidence.machine_receipt.restored_member_count != RECOVERY_MEMBER_COUNT:
        raise PrivateEvidenceRecoveryOpsError("operator drill did not restore both members")
