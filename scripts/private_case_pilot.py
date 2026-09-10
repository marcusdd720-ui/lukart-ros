"""Run CASE-OPS-06 against private local case inputs only."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_case_pilot_v1 import (
    PILOT_INPUT_PRIVATE,
    PrivateCasePilotError,
    load_ledger_bundle_file,
    load_runtime_identity_file,
    run_private_local_pilot,
    write_pilot_receipt,
)
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_recovery_v1 import RecoveredEvidenceKeyProvider
from core.private_evidence_v1 import PrivateEvidenceStore
from knowledge.models.case_manifest import CaseManifest

ROOT = Path(__file__).resolve().parents[1]


def _outside_repo(path: Path, *, label: str) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = candidate.resolve()
    root = ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(f"{label} must be outside the public repository")
    return resolved


def _parse_keys(values: list[list[str]]) -> tuple[RecoveredEvidenceKeyProvider, str, int]:
    keys: dict[tuple[str, int], bytes] = {}
    last: tuple[str, int] | None = None
    for raw_id, raw_version, raw_path in values:
        key_id = raw_id.strip()
        try:
            key_version = int(raw_version)
        except ValueError as exc:
            raise ValueError("key version must be an integer") from exc
        identity = (key_id, key_version)
        if not key_id or key_version < 1 or identity in keys:
            raise ValueError("key bindings must be unique valid id/version pairs")
        key_path = _outside_repo(Path(raw_path), label="evidence key file")
        provider = LocalFileEvidenceKeyProvider(
            key_path,
            key_id=key_id,
            key_version=key_version,
        )
        keys[identity] = provider.get_key(key_id, key_version)
        last = identity
    if last is None:
        raise ValueError("at least one evidence key is required")
    return RecoveredEvidenceKeyProvider(keys), last[0], last[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify private evidence -> CCL -> Product runtime -> replay end to end"
    )
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--ccl-bundle", required=True)
    parser.add_argument("--runtime-identity", required=True)
    parser.add_argument("--receipt-out", required=True)
    parser.add_argument("--subject-id", default="local-private-pilot-operator")
    parser.add_argument(
        "--key",
        nargs=3,
        action="append",
        required=True,
        metavar=("KEY_ID", "VERSION", "FILE"),
        help="Repeat for every historical/active evidence key; put the active key last",
    )
    parser.add_argument(
        "--confirm-private-local-case",
        action="store_true",
        help="Explicit operator declaration; never inferred by CI",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if not args.confirm_private_local_case:
            raise PrivateCasePilotError(
                "real pilot requires explicit --confirm-private-local-case declaration"
            )
        data_root = ensure_data_root(
            Path(args.data_root).expanduser() if args.data_root else None,
            repo_root=ROOT,
        )
        key = validate_case_key(args.case)
        case_root = case_dir(key, data_root, repo_root=ROOT)
        if not case_root.is_dir():
            raise FileNotFoundError(f"local case does not exist: {case_root}")
        case_id = CaseManifest.load(case_root).case_id
        authorization = AuthorizationContext(
            subject_id=args.subject_id,
            tenant_id=args.tenant_id,
            roles=("local-private-pilot-operator",),
            permissions=(Permission.EVIDENCE_READ,),
            case_ids=(case_id,),
        )
        key_provider, active_key_id, active_key_version = _parse_keys(args.key)
        store = PrivateEvidenceStore(
            case_root / ".private-evidence",
            key_provider=key_provider,
            authorization=authorization,
            tenant_id=args.tenant_id,
            case_id=case_id,
            key_id=active_key_id,
            key_version=active_key_version,
        )
        bundle_path = _outside_repo(Path(args.ccl_bundle), label="CCL bundle")
        runtime_path = _outside_repo(
            Path(args.runtime_identity),
            label="runtime identity",
        )
        receipt_target = Path(args.receipt_out).expanduser()
        bundle = load_ledger_bundle_file(bundle_path)
        runtime_identity = load_runtime_identity_file(runtime_path)
        run = run_private_local_pilot(
            evidence_store=store,
            ledger_bundle=bundle,
            runtime_identity=runtime_identity,
            input_class=PILOT_INPUT_PRIVATE,
        )
        receipt_path = write_pilot_receipt(
            run.receipt,
            receipt_target,
            repo_root=ROOT,
        )
        print("PRIVATE LOCAL PILOT MACHINE PASS")
        print("Pilot receipt ID:", run.receipt.receipt_id)
        print("Private projection ID:", run.receipt.private_projection_id)
        print("CCL bundle digest:", run.receipt.ccl_bundle_digest)
        print("Product runtime proof:", run.receipt.product_runtime_proof_digest)
        print("Replay manifest:", run.receipt.replay_manifest_digest)
        print("Receipt:", receipt_path)
        print("Real private data persisted in receipt: false")
        print("Independent review claimed: false")
        return 0
    except (OSError, ValueError, RuntimeError, PrivateCasePilotError) as exc:
        print("PRIVATE LOCAL PILOT FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
