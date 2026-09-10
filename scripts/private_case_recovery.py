"""Operate CASE-OPS-03/04/05 local recovery without persisting recovery secrets."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_recovery_ops_v1 import (
    PrivateEvidenceRecoveryOpsError,
    RecoveryOperatorAssertionsV1,
    load_recovery_set_record,
    rotate_recovery_set_secrets,
    run_operator_recovery_drill,
    write_operator_drill_evidence,
    write_redundant_recovery_set_records,
    write_rotation_receipt,
)
from core.private_evidence_recovery_set_v1 import (
    PrivateEvidenceRecoverySetError,
    create_redundant_recovery_set,
    verify_redundant_recovery_set,
)
from core.private_evidence_recovery_v1 import (
    PrivateEvidenceRecoveryError,
    create_recovery_capsule,
    restore_recovery_capsule,
    verify_recovery_capsule,
)
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore
from knowledge.models.case_manifest import CaseManifest

ROOT = Path(__file__).resolve().parents[1]


class MultiFileEvidenceKeyProvider:
    """Compose exact local key files without persisting a new aggregate key file."""

    def __init__(
        self,
        bindings: list[tuple[str, int, Path]],
    ) -> None:
        self._providers: dict[tuple[str, int], LocalFileEvidenceKeyProvider] = {}
        for key_id, key_version, key_file in bindings:
            identity = (key_id.strip(), key_version)
            if not identity[0] or key_version < 1 or identity in self._providers:
                raise ValueError("key bindings must have unique nonblank id/version")
            provider = LocalFileEvidenceKeyProvider(
                key_file,
                key_id=identity[0],
                key_version=identity[1],
            )
            resolved = provider.key_file
            if resolved == ROOT or ROOT in resolved.parents:
                raise ValueError("evidence key files must be outside the public repository tree")
            self._providers[identity] = provider

    def get_key(self, key_id: str, key_version: int) -> bytes:
        try:
            provider = self._providers[(key_id.strip(), key_version)]
        except KeyError as exc:
            raise PrivateEvidenceError("requested evidence key identity is unavailable") from exc
        return provider.get_key(key_id, key_version)


def _authorization(
    *,
    subject_id: str,
    tenant_id: str,
    case_id: str,
    write: bool,
) -> AuthorizationContext:
    permissions = [Permission.EVIDENCE_READ]
    if write:
        permissions.append(Permission.EVIDENCE_WRITE)
    return AuthorizationContext(
        subject_id=subject_id,
        tenant_id=tenant_id,
        roles=("local-case-recovery-operator",),
        permissions=tuple(permissions),
        case_ids=(case_id,),
    )


def _passphrase(label: str, *, confirm: bool) -> str:
    first = getpass.getpass(f"{label}: ")
    if confirm:
        second = getpass.getpass(f"Confirm {label.lower()}: ")
        if first != second:
            raise ValueError(f"{label.lower()} confirmation does not match")
    return first


def _two_passphrases(*, prefix: str) -> tuple[str, str]:
    first = _passphrase(f"{prefix} A", confirm=True)
    second = _passphrase(f"{prefix} B", confirm=True)
    if first == second:
        raise ValueError("recovery-set passphrases must be independent")
    return first, second


def _parse_key_bindings(values: list[list[str]]) -> list[tuple[str, int, Path]]:
    parsed: list[tuple[str, int, Path]] = []
    for key_id, raw_version, raw_path in values:
        try:
            version = int(raw_version)
        except ValueError as exc:
            raise ValueError("key version must be an integer") from exc
        parsed.append((key_id, version, Path(raw_path).expanduser()))
    return parsed


def _add_case_key_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--active-key-id", required=True)
    parser.add_argument("--active-key-version", type=int, required=True)
    parser.add_argument(
        "--key",
        nargs=3,
        action="append",
        required=True,
        metavar=("KEY_ID", "VERSION", "FILE"),
        help="Repeat for every historical/active evidence key required by the store",
    )
    parser.add_argument("--subject-id", default="local-case-recovery-operator")


def _add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--subject-id", default="local-case-recovery-operator")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CASE-OPS local recovery capsule, redundant-set, drill, and rotation operations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create one CASE-OPS-03 recovery capsule")
    _add_case_key_arguments(create)
    create.add_argument("destination", help="Destination ending in .mvros-recovery")

    verify = subparsers.add_parser("verify", help="Verify one CASE-OPS-03 recovery capsule")
    verify.add_argument("capsule")
    _add_scope_arguments(verify)

    restore = subparsers.add_parser("restore", help="Restore one CASE-OPS-03 recovery capsule")
    restore.add_argument("capsule")
    restore.add_argument("destination")
    _add_scope_arguments(restore)

    set_create = subparsers.add_parser(
        "set-create",
        help="Create a CASE-OPS-04 1-of-2 set and redundant digest-only records",
    )
    _add_case_key_arguments(set_create)
    set_create.add_argument("destination_a")
    set_create.add_argument("destination_b")

    set_verify = subparsers.add_parser(
        "set-verify",
        help="Verify both exact members of a CASE-OPS-04 recovery set",
    )
    set_verify.add_argument("record")
    set_verify.add_argument("capsule_a")
    set_verify.add_argument("capsule_b")
    _add_scope_arguments(set_verify)

    set_drill = subparsers.add_parser(
        "set-drill",
        help="Restore both members and emit CASE-OPS-05 operator drill evidence",
    )
    set_drill.add_argument("record")
    set_drill.add_argument("capsule_a")
    set_drill.add_argument("capsule_b")
    set_drill.add_argument("restore_a")
    set_drill.add_argument("restore_b")
    set_drill.add_argument("--receipt-out", required=True)
    set_drill.add_argument("--assert-source-workstation-unavailable", action="store_true")
    set_drill.add_argument("--assert-network-disconnected", action="store_true")
    set_drill.add_argument("--assert-media-physically-separate", action="store_true")
    set_drill.add_argument("--assert-recovery-secrets-separately-custodied", action="store_true")
    _add_scope_arguments(set_drill)

    set_rotate = subparsers.add_parser(
        "set-rotate",
        help="Rotate recovery secrets from one surviving CASE-OPS-04 member",
    )
    set_rotate.add_argument("record")
    set_rotate.add_argument("source_slot", choices=("A", "B"))
    set_rotate.add_argument("source_capsule")
    set_rotate.add_argument("staging_parent")
    set_rotate.add_argument("destination_a")
    set_rotate.add_argument("destination_b")
    set_rotate.add_argument("--receipt-out", required=True)
    _add_scope_arguments(set_rotate)
    return parser


def _case_store(args: argparse.Namespace) -> tuple[str, PrivateEvidenceStore]:
    data_root = ensure_data_root(
        Path(args.data_root).expanduser() if args.data_root else None,
        repo_root=ROOT,
    )
    case_key = validate_case_key(args.case)
    target = case_dir(case_key, data_root, repo_root=ROOT)
    if not target.is_dir():
        raise FileNotFoundError(f"Local case does not exist: {target}")
    case_id = CaseManifest.load(target).case_id
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=case_id,
        write=True,
    )
    provider = MultiFileEvidenceKeyProvider(_parse_key_bindings(args.key))
    store = PrivateEvidenceStore(
        target / ".private-evidence",
        key_provider=provider,
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=case_id,
        key_id=args.active_key_id,
        key_version=args.active_key_version,
    )
    return case_key, store


def _create(args: argparse.Namespace) -> int:
    _case_key, store = _case_store(args)
    result = create_recovery_capsule(
        store,
        Path(args.destination),
        passphrase=_passphrase("Recovery passphrase", confirm=True),
        repo_root=ROOT,
    )
    print("RECOVERY CREATE PASS")
    print("Capsule:", result.capsule_path)
    print("Capsule ID:", result.capsule_id)
    print("Snapshot:", result.snapshot_digest)
    print("Encrypted files:", result.file_count)
    print("Encrypted bytes:", result.total_bytes)
    return 0


def _verify(args: argparse.Namespace) -> int:
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        write=False,
    )
    result = verify_recovery_capsule(
        Path(args.capsule),
        passphrase=_passphrase("Recovery passphrase", confirm=False),
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        repo_root=ROOT,
    )
    print("RECOVERY VERIFY PASS")
    print("Capsule ID:", result.capsule_id)
    print("Snapshot:", result.snapshot_digest)
    print("Encrypted files:", result.file_count)
    print("Recovered key identities:", len(result.key_provider.identities))
    return 0


def _restore(args: argparse.Namespace) -> int:
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        write=True,
    )
    result = restore_recovery_capsule(
        Path(args.capsule),
        Path(args.destination),
        passphrase=_passphrase("Recovery passphrase", confirm=False),
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        repo_root=ROOT,
    )
    print("RECOVERY RESTORE PASS")
    print("Capsule ID:", result.capsule_id)
    print("Snapshot:", result.snapshot_digest)
    print("Restored encrypted evidence:", result.store.root)
    print("Recovered key identities:", len(result.key_provider.identities))
    print("Raw keys persisted: false")
    return 0


def _set_create(args: argparse.Namespace) -> int:
    _case_key, store = _case_store(args)
    result = create_redundant_recovery_set(
        store,
        (Path(args.destination_a), Path(args.destination_b)),
        passphrases=_two_passphrases(prefix="Recovery passphrase"),
        repo_root=ROOT,
    )
    records = write_redundant_recovery_set_records(
        result.recovery_set,
        result.member_paths,
        repo_root=ROOT,
    )
    print("RECOVERY SET CREATE PASS")
    print("Recovery set ID:", result.recovery_set.recovery_set_id)
    print("Snapshot:", result.recovery_set.snapshot_digest)
    print("Member A capsule ID:", result.recovery_set.members[0].capsule_id)
    print("Member B capsule ID:", result.recovery_set.members[1].capsule_id)
    print("Record A:", records[0])
    print("Record B:", records[1])
    return 0


def _set_verify(args: argparse.Namespace) -> int:
    recovery_set = load_recovery_set_record(Path(args.record))
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        write=False,
    )
    set_id = verify_redundant_recovery_set(
        recovery_set,
        (Path(args.capsule_a), Path(args.capsule_b)),
        passphrases=_two_passphrases(prefix="Recovery passphrase"),
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        repo_root=ROOT,
    )
    print("RECOVERY SET VERIFY PASS")
    print("Recovery set ID:", set_id)
    print("Snapshot:", recovery_set.snapshot_digest)
    return 0


def _set_drill(args: argparse.Namespace) -> int:
    recovery_set = load_recovery_set_record(Path(args.record))
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        write=True,
    )
    assertions = RecoveryOperatorAssertionsV1(
        source_workstation_unavailable=args.assert_source_workstation_unavailable,
        network_disconnected=args.assert_network_disconnected,
        media_physically_separate=args.assert_media_physically_separate,
        recovery_secrets_separately_custodied=(
            args.assert_recovery_secrets_separately_custodied
        ),
    )
    evidence = run_operator_recovery_drill(
        recovery_set,
        (Path(args.capsule_a), Path(args.capsule_b)),
        (Path(args.restore_a), Path(args.restore_b)),
        passphrases=_two_passphrases(prefix="Recovery passphrase"),
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        assertions=assertions,
        repo_root=ROOT,
    )
    receipt_path = write_operator_drill_evidence(
        evidence,
        Path(args.receipt_out),
        repo_root=ROOT,
    )
    print("RECOVERY SET DRILL MACHINE PASS")
    print("Machine receipt ID:", evidence.machine_receipt.receipt_id)
    print("Operator evidence ID:", evidence.evidence_id)
    print("Operator evidence status:", evidence.status)
    print("Receipt:", receipt_path)
    if not assertions.complete:
        print("RECOVERY SET DRILL INCOMPLETE: physical/offline assertions are incomplete")
        return 1
    return 0


def _set_rotate(args: argparse.Namespace) -> int:
    recovery_set = load_recovery_set_record(Path(args.record))
    authorization = _authorization(
        subject_id=args.subject_id,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        write=True,
    )
    old_passphrase = _passphrase("Surviving recovery passphrase", confirm=False)
    new_passphrases = _two_passphrases(prefix="New recovery passphrase")
    result = rotate_recovery_set_secrets(
        recovery_set,
        source_slot=args.source_slot,
        source_capsule=Path(args.source_capsule),
        old_passphrase=old_passphrase,
        staging_parent=Path(args.staging_parent),
        new_destinations=(Path(args.destination_a), Path(args.destination_b)),
        new_passphrases=new_passphrases,
        authorization=authorization,
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        repo_root=ROOT,
    )
    records = write_redundant_recovery_set_records(
        result.recovery_set_result.recovery_set,
        result.recovery_set_result.member_paths,
        repo_root=ROOT,
    )
    receipt_path = write_rotation_receipt(
        result.receipt,
        Path(args.receipt_out),
        repo_root=ROOT,
    )
    print("RECOVERY SET ROTATION PASS")
    print("Old recovery set ID:", result.receipt.old_recovery_set_id)
    print("New recovery set ID:", result.receipt.new_recovery_set_id)
    print("Snapshot preserved:", result.receipt.snapshot_digest)
    print("Record A:", records[0])
    print("Record B:", records[1])
    print("Rotation receipt:", receipt_path)
    print("Old recovery members automatically deleted: false")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        handlers = {
            "create": _create,
            "verify": _verify,
            "restore": _restore,
            "set-create": _set_create,
            "set-verify": _set_verify,
            "set-drill": _set_drill,
            "set-rotate": _set_rotate,
        }
        handler = handlers.get(args.command)
        if handler is None:
            raise ValueError("unsupported recovery command")
        return handler(args)
    except (
        OSError,
        ValueError,
        RuntimeError,
        PrivateEvidenceRecoveryError,
        PrivateEvidenceRecoverySetError,
        PrivateEvidenceRecoveryOpsError,
    ) as exc:
        print("RECOVERY FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
