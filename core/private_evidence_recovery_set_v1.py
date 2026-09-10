"""Redundant offline recovery sets for CASE-OPS-04.

CASE-OPS-04 composes the verified CASE-OPS-03 recovery capsule rather than
creating a second evidence or case-history authority. A v1 recovery set has two
independently wrapped capsules on two devices that are also distinct from the
live private-evidence device. Either member can restore the exact same encrypted
evidence snapshot.
"""

from __future__ import annotations

import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext
from core.private_evidence_recovery_v1 import (
    RECOVERY_SUFFIX,
    PrivateEvidenceRecoveryError,
    RestoredPrivateEvidenceV1,
    create_recovery_capsule,
    restore_recovery_capsule,
    verify_recovery_capsule,
)
from core.private_evidence_v1 import PrivateEvidenceStore, digest_hex, digest_object

SCHEMA_RECOVERY_SET = "lukart.private-evidence-recovery-set.v1"
SCHEMA_RECOVERY_DRILL = "lukart.private-evidence-recovery-drill.v1"
RECOVERY_SET_PROFILE = "REDUNDANT_1_OF_2_DISTINCT_DEVICE_V1"
RECOVERY_DEVICE_POLICY = "SOURCE_PLUS_TWO_DISTINCT_FILESYSTEM_DEVICES"
RECOVERY_MEMBER_SLOTS = ("A", "B")
RECOVERY_MEMBER_COUNT = 2
RECOVERY_THRESHOLD = 1


class PrivateEvidenceRecoverySetError(RuntimeError):
    """Fail-closed error at the CASE-OPS-04 recovery-set boundary."""


@dataclass(frozen=True, slots=True)
class RecoverySetMemberV1:
    slot: str
    capsule_id: str
    snapshot_digest: str
    key_envelope_digest: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "slot": self.slot,
            "capsule_id": self.capsule_id,
            "snapshot_digest": self.snapshot_digest,
            "key_envelope_digest": self.key_envelope_digest,
        }


@dataclass(frozen=True, slots=True)
class RecoverySetV1:
    schema: str
    profile: str
    device_policy: str
    case_scope_digest: str
    snapshot_digest: str
    recovery_threshold: int
    member_count: int
    members: tuple[RecoverySetMemberV1, RecoverySetMemberV1]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile": self.profile,
            "device_policy": self.device_policy,
            "case_scope_digest": self.case_scope_digest,
            "snapshot_digest": self.snapshot_digest,
            "recovery_threshold": self.recovery_threshold,
            "member_count": self.member_count,
            "members": [member.canonical_dict() for member in self.members],
        }

    @property
    def recovery_set_id(self) -> str:
        return digest_object(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> RecoverySetV1:
        expected = {
            "schema",
            "profile",
            "device_policy",
            "case_scope_digest",
            "snapshot_digest",
            "recovery_threshold",
            "member_count",
            "members",
        }
        if set(value) != expected:
            raise PrivateEvidenceRecoverySetError("unknown or missing recovery-set fields")
        if value.get("schema") != SCHEMA_RECOVERY_SET:
            raise PrivateEvidenceRecoverySetError("unsupported recovery-set schema")
        if value.get("profile") != RECOVERY_SET_PROFILE:
            raise PrivateEvidenceRecoverySetError("unsupported recovery-set profile")
        if value.get("device_policy") != RECOVERY_DEVICE_POLICY:
            raise PrivateEvidenceRecoverySetError("unsupported recovery-set device policy")
        case_scope_digest = _content_id(value.get("case_scope_digest"), "case scope digest")
        snapshot_digest = _content_id(value.get("snapshot_digest"), "snapshot digest")
        if value.get("recovery_threshold") != RECOVERY_THRESHOLD:
            raise PrivateEvidenceRecoverySetError("unsupported recovery threshold")
        if value.get("member_count") != RECOVERY_MEMBER_COUNT:
            raise PrivateEvidenceRecoverySetError("unsupported recovery member count")
        raw_members = value.get("members")
        if not isinstance(raw_members, list) or len(raw_members) != RECOVERY_MEMBER_COUNT:
            raise PrivateEvidenceRecoverySetError("recovery members must contain exactly two items")
        parsed = tuple(_parse_member(item) for item in raw_members)
        if len(parsed) != 2:
            raise PrivateEvidenceRecoverySetError("recovery members must contain exactly two items")
        members = (parsed[0], parsed[1])
        _validate_members(members, snapshot_digest=snapshot_digest)
        return cls(
            schema=SCHEMA_RECOVERY_SET,
            profile=RECOVERY_SET_PROFILE,
            device_policy=RECOVERY_DEVICE_POLICY,
            case_scope_digest=case_scope_digest,
            snapshot_digest=snapshot_digest,
            recovery_threshold=RECOVERY_THRESHOLD,
            member_count=RECOVERY_MEMBER_COUNT,
            members=members,
        )


@dataclass(frozen=True, slots=True)
class RecoverySetResultV1:
    recovery_set: RecoverySetV1
    member_paths: tuple[Path, Path]


@dataclass(frozen=True, slots=True)
class RecoveryDrillReceiptV1:
    schema: str
    profile: str
    case_scope_digest: str
    recovery_set_id: str
    snapshot_digest: str
    restored_member_count: int
    key_identity_digest: str
    result: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile": self.profile,
            "case_scope_digest": self.case_scope_digest,
            "recovery_set_id": self.recovery_set_id,
            "snapshot_digest": self.snapshot_digest,
            "restored_member_count": self.restored_member_count,
            "key_identity_digest": self.key_identity_digest,
            "result": self.result,
        }

    @property
    def receipt_id(self) -> str:
        return digest_object(self.canonical_dict())


def _content_id(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise PrivateEvidenceRecoverySetError(f"{label} must be a sha256 content identifier")
    try:
        digest_hex(value)
    except Exception as exc:
        raise PrivateEvidenceRecoverySetError(
            f"{label} must be a sha256 content identifier"
        ) from exc
    return value


def _parse_member(value: object) -> RecoverySetMemberV1:
    if not isinstance(value, dict):
        raise PrivateEvidenceRecoverySetError("recovery-set member must be a mapping")
    expected = {"slot", "capsule_id", "snapshot_digest", "key_envelope_digest"}
    if set(value) != expected:
        raise PrivateEvidenceRecoverySetError("unknown or missing recovery-set member fields")
    slot = value.get("slot")
    if not isinstance(slot, str):
        raise PrivateEvidenceRecoverySetError("recovery-set member slot must be text")
    return RecoverySetMemberV1(
        slot=slot,
        capsule_id=_content_id(value.get("capsule_id"), "member capsule id"),
        snapshot_digest=_content_id(value.get("snapshot_digest"), "member snapshot digest"),
        key_envelope_digest=_content_id(
            value.get("key_envelope_digest"), "member key-envelope digest"
        ),
    )


def _validate_members(
    members: tuple[RecoverySetMemberV1, RecoverySetMemberV1],
    *,
    snapshot_digest: str,
) -> None:
    if tuple(member.slot for member in members) != RECOVERY_MEMBER_SLOTS:
        raise PrivateEvidenceRecoverySetError("recovery-set member slots must be canonical A, B")
    if any(member.snapshot_digest != snapshot_digest for member in members):
        raise PrivateEvidenceRecoverySetError("recovery-set members do not share one snapshot")
    if len({member.capsule_id for member in members}) != RECOVERY_MEMBER_COUNT:
        raise PrivateEvidenceRecoverySetError("recovery-set capsule identities must be distinct")
    if len({member.key_envelope_digest for member in members}) != RECOVERY_MEMBER_COUNT:
        raise PrivateEvidenceRecoverySetError(
            "recovery-set key-envelope identities must be independently wrapped"
        )


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _existing_parent(target: Path) -> Path:
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise PrivateEvidenceRecoverySetError(
            "recovery-set destination parent must already exist and must not be a symlink"
        )
    return parent.resolve()


def _device_id(path: Path) -> int:
    if path.is_symlink() or not path.exists():
        raise PrivateEvidenceRecoverySetError("filesystem device probe target is invalid")
    try:
        return int(os.stat(path).st_dev)
    except OSError as exc:
        raise PrivateEvidenceRecoverySetError("filesystem device identity is unavailable") from exc


def _preflight_devices(store: PrivateEvidenceStore, destinations: tuple[Path, Path]) -> None:
    source_device = _device_id(store.root)
    target_devices = tuple(_device_id(_existing_parent(target)) for target in destinations)
    if source_device in target_devices or len(set(target_devices)) != RECOVERY_MEMBER_COUNT:
        raise PrivateEvidenceRecoverySetError(
            "CASE-OPS-04 requires two recovery devices distinct from each other and the live store"
        )


def _stage_path(target: Path, slot: str) -> Path:
    stem = target.name[: -len(RECOVERY_SUFFIX)] if target.name.endswith(RECOVERY_SUFFIX) else target.name
    return target.parent / f".{stem}.slot-{slot.lower()}.{secrets.token_hex(8)}{RECOVERY_SUFFIX}"


def _case_scope_digest(tenant_id: str, case_id: str) -> str:
    return digest_object({"tenant_id": tenant_id.strip(), "case_id": case_id.strip()})


def create_redundant_recovery_set(
    store: PrivateEvidenceStore,
    destinations: tuple[Path, Path],
    *,
    passphrases: tuple[str, str],
    repo_root: Path | None = None,
) -> RecoverySetResultV1:
    """Create two independently wrapped CASE-OPS-03 capsules on distinct devices."""
    targets = (_absolute(destinations[0]), _absolute(destinations[1]))
    if targets[0] == targets[1]:
        raise PrivateEvidenceRecoverySetError("recovery-set destinations must be distinct")
    if passphrases[0] == passphrases[1]:
        raise PrivateEvidenceRecoverySetError("recovery-set passphrases must be independent")
    if any(target.exists() for target in targets):
        raise PrivateEvidenceRecoverySetError("recovery-set destination already exists")
    if any(not target.name.endswith(RECOVERY_SUFFIX) for target in targets):
        raise PrivateEvidenceRecoverySetError(
            f"recovery-set destinations must end with {RECOVERY_SUFFIX}"
        )
    _preflight_devices(store, targets)

    stages = (
        _stage_path(targets[0], RECOVERY_MEMBER_SLOTS[0]),
        _stage_path(targets[1], RECOVERY_MEMBER_SLOTS[1]),
    )
    published: list[Path] = []
    try:
        first = create_recovery_capsule(
            store,
            stages[0],
            passphrase=passphrases[0],
            repo_root=repo_root,
        )
        second = create_recovery_capsule(
            store,
            stages[1],
            passphrase=passphrases[1],
            repo_root=repo_root,
        )
        if first.snapshot_digest != second.snapshot_digest:
            raise PrivateEvidenceRecoverySetError(
                "live evidence changed while redundant recovery members were created"
            )
        members = (
            RecoverySetMemberV1(
                slot="A",
                capsule_id=first.capsule_id,
                snapshot_digest=first.snapshot_digest,
                key_envelope_digest=first.key_envelope_digest,
            ),
            RecoverySetMemberV1(
                slot="B",
                capsule_id=second.capsule_id,
                snapshot_digest=second.snapshot_digest,
                key_envelope_digest=second.key_envelope_digest,
            ),
        )
        _validate_members(members, snapshot_digest=first.snapshot_digest)
        for stage, target in zip(stages, targets, strict=True):
            os.replace(stage, target)
            published.append(target)
        recovery_set = RecoverySetV1(
            schema=SCHEMA_RECOVERY_SET,
            profile=RECOVERY_SET_PROFILE,
            device_policy=RECOVERY_DEVICE_POLICY,
            case_scope_digest=store.case_scope_digest,
            snapshot_digest=first.snapshot_digest,
            recovery_threshold=RECOVERY_THRESHOLD,
            member_count=RECOVERY_MEMBER_COUNT,
            members=members,
        )
        verify_redundant_recovery_set(
            recovery_set,
            targets,
            passphrases=passphrases,
            authorization=store.authorization,
            tenant_id=store.tenant_id,
            case_id=store.case_id,
            repo_root=repo_root,
        )
        return RecoverySetResultV1(recovery_set=recovery_set, member_paths=targets)
    except Exception:
        for path in (*stages, *published):
            shutil.rmtree(path, ignore_errors=True)
        raise


def verify_redundant_recovery_set(
    recovery_set: RecoverySetV1,
    member_paths: tuple[Path, Path],
    *,
    passphrases: tuple[str, str],
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> str:
    """Verify exact member identities, independent wrapping, and current device separation."""
    parsed = RecoverySetV1.from_dict(recovery_set.canonical_dict())
    expected_scope = _case_scope_digest(tenant_id, case_id)
    if parsed.case_scope_digest != expected_scope:
        raise PrivateEvidenceRecoverySetError("recovery-set case scope mismatch")
    if passphrases[0] == passphrases[1]:
        raise PrivateEvidenceRecoverySetError("recovery-set passphrases must be independent")
    paths = (_absolute(member_paths[0]), _absolute(member_paths[1]))
    if paths[0] == paths[1] or _device_id(paths[0]) == _device_id(paths[1]):
        raise PrivateEvidenceRecoverySetError(
            "recovery-set members must currently reside on distinct filesystem devices"
        )
    for member, path, passphrase in zip(parsed.members, paths, passphrases, strict=True):
        verified = verify_recovery_capsule(
            path,
            passphrase=passphrase,
            authorization=authorization,
            tenant_id=tenant_id,
            case_id=case_id,
            repo_root=repo_root,
        )
        if (
            verified.capsule_id != member.capsule_id
            or verified.snapshot_digest != member.snapshot_digest
            or verified.key_envelope_digest != member.key_envelope_digest
        ):
            raise PrivateEvidenceRecoverySetError(
                f"recovery-set member {member.slot} identity mismatch"
            )
    return parsed.recovery_set_id


def restore_recovery_set_member(
    recovery_set: RecoverySetV1,
    *,
    slot: str,
    capsule_path: Path,
    passphrase: str,
    destination: Path,
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> RestoredPrivateEvidenceV1:
    """Restore from one exact member; the other recovery member is not required."""
    parsed = RecoverySetV1.from_dict(recovery_set.canonical_dict())
    expected_scope = _case_scope_digest(tenant_id, case_id)
    if parsed.case_scope_digest != expected_scope:
        raise PrivateEvidenceRecoverySetError("recovery-set case scope mismatch")
    member = next((item for item in parsed.members if item.slot == slot), None)
    if member is None:
        raise PrivateEvidenceRecoverySetError("unknown recovery-set member slot")
    verified = verify_recovery_capsule(
        capsule_path,
        passphrase=passphrase,
        authorization=authorization,
        tenant_id=tenant_id,
        case_id=case_id,
        repo_root=repo_root,
    )
    if (
        verified.capsule_id != member.capsule_id
        or verified.snapshot_digest != parsed.snapshot_digest
        or verified.key_envelope_digest != member.key_envelope_digest
    ):
        raise PrivateEvidenceRecoverySetError("selected recovery-set member identity mismatch")
    return restore_recovery_capsule(
        capsule_path,
        destination,
        passphrase=passphrase,
        authorization=authorization,
        tenant_id=tenant_id,
        case_id=case_id,
        repo_root=repo_root,
    )


def run_recovery_set_drill(
    recovery_set: RecoverySetV1,
    member_paths: tuple[Path, Path],
    restore_targets: tuple[Path, Path],
    *,
    passphrases: tuple[str, str],
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> RecoveryDrillReceiptV1:
    """Verify both independent members and prove that each can restore the exact snapshot."""
    set_id = verify_redundant_recovery_set(
        recovery_set,
        member_paths,
        passphrases=passphrases,
        authorization=authorization,
        tenant_id=tenant_id,
        case_id=case_id,
        repo_root=repo_root,
    )
    if restore_targets[0] == restore_targets[1]:
        raise PrivateEvidenceRecoverySetError("recovery drill restore targets must be distinct")
    restored_paths: list[Path] = []
    restored: list[RestoredPrivateEvidenceV1] = []
    try:
        for member, capsule_path, passphrase, target in zip(
            recovery_set.members,
            member_paths,
            passphrases,
            restore_targets,
            strict=True,
        ):
            result = restore_recovery_set_member(
                recovery_set,
                slot=member.slot,
                capsule_path=capsule_path,
                passphrase=passphrase,
                destination=target,
                authorization=authorization,
                tenant_id=tenant_id,
                case_id=case_id,
                repo_root=repo_root,
            )
            restored.append(result)
            restored_paths.append(result.store.root)
        identities = restored[0].key_provider.identities
        if any(result.snapshot_digest != recovery_set.snapshot_digest for result in restored):
            raise PrivateEvidenceRecoverySetError("recovery drill restored snapshot mismatch")
        if any(result.key_provider.identities != identities for result in restored):
            raise PrivateEvidenceRecoverySetError("recovery drill restored key identity mismatch")
        key_identity_digest = digest_object(
            {
                "identities": [
                    {"key_id": key_id, "key_version": key_version}
                    for key_id, key_version in identities
                ]
            }
        )
        return RecoveryDrillReceiptV1(
            schema=SCHEMA_RECOVERY_DRILL,
            profile=RECOVERY_SET_PROFILE,
            case_scope_digest=recovery_set.case_scope_digest,
            recovery_set_id=set_id,
            snapshot_digest=recovery_set.snapshot_digest,
            restored_member_count=RECOVERY_MEMBER_COUNT,
            key_identity_digest=key_identity_digest,
            result="PASS",
        )
    except Exception:
        for path in restored_paths:
            shutil.rmtree(path, ignore_errors=True)
        raise
