"""Create, verify, and restore CASE-OPS-03 offline local recovery capsules."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
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


def _passphrase(*, confirm: bool) -> str:
    first = getpass.getpass("Recovery passphrase: ")
    if confirm:
        second = getpass.getpass("Confirm recovery passphrase: ")
        if first != second:
            raise ValueError("recovery passphrase confirmation does not match")
    return first


def _parse_key_bindings(values: list[list[str]]) -> list[tuple[str, int, Path]]:
    parsed: list[tuple[str, int, Path]] = []
    for key_id, raw_version, raw_path in values:
        try:
            version = int(raw_version)
        except ValueError as exc:
            raise ValueError("key version must be an integer") from exc
        parsed.append((key_id, version, Path(raw_path).expanduser()))
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CASE-OPS-03 offline local recovery capsule operations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create an authenticated recovery capsule")
    create.add_argument("case", help="Private local case key")
    create.add_argument("destination", help="Destination ending in .mvros-recovery")
    create.add_argument("--data-root", default=None, help="Private local MVROS data root")
    create.add_argument("--tenant-id", required=True)
    create.add_argument("--active-key-id", required=True)
    create.add_argument("--active-key-version", type=int, required=True)
    create.add_argument(
        "--key",
        nargs=3,
        action="append",
        required=True,
        metavar=("KEY_ID", "VERSION", "FILE"),
        help="Repeat for every historical/active evidence key required by the store",
    )
    create.add_argument("--subject-id", default="local-case-recovery-operator")

    verify = subparsers.add_parser("verify", help="Verify capsule integrity and key recovery")
    verify.add_argument("capsule")
    verify.add_argument("--tenant-id", required=True)
    verify.add_argument("--case-id", required=True)
    verify.add_argument("--subject-id", default="local-case-recovery-operator")

    restore = subparsers.add_parser("restore", help="Restore encrypted evidence from a capsule")
    restore.add_argument("capsule")
    restore.add_argument("destination")
    restore.add_argument("--tenant-id", required=True)
    restore.add_argument("--case-id", required=True)
    restore.add_argument("--subject-id", default="local-case-recovery-operator")
    return parser


def _create(args: argparse.Namespace) -> int:
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
    result = create_recovery_capsule(
        store,
        Path(args.destination),
        passphrase=_passphrase(confirm=True),
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
        passphrase=_passphrase(confirm=False),
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
        passphrase=_passphrase(confirm=False),
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


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.command == "create":
            return _create(args)
        if args.command == "verify":
            return _verify(args)
        if args.command == "restore":
            return _restore(args)
        raise ValueError("unsupported recovery command")
    except (OSError, ValueError, RuntimeError, PrivateEvidenceRecoveryError) as exc:
        print("RECOVERY FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
