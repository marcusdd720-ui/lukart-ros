"""Run CASE-OPS-07 observed OCR replay against private local evidence only."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_recovery_v1 import RecoveredEvidenceKeyProvider
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore
from core.private_ocr_replay_v1 import (
    verify_environment_bound_ocr_replay,
    write_ocr_replay_proof,
)
from knowledge.models.case_manifest import CaseManifest

ROOT = Path(__file__).resolve().parents[1]


def _outside_repo(path: Path, *, label: str) -> Path:
    absolute = Path(os.path.abspath(path.expanduser()))
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and candidate.is_symlink():
            raise ValueError(f"{label} must not traverse symlinks")
    resolved = absolute.resolve()
    root = ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(f"{label} must be outside the public repository")
    return resolved


def _parse_keys(values: list[list[str]]) -> tuple[RecoveredEvidenceKeyProvider, str, int]:
    keys: dict[tuple[str, int], bytes] = {}
    active: tuple[str, int] | None = None
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
        active = identity
    if active is None:
        raise ValueError("at least one evidence key is required")
    return RecoveredEvidenceKeyProvider(keys), active[0], active[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay one CASE-OPS-02 ENVIRONMENT_BOUND Tesseract derivation and emit a "
            "digest-only CASE-OPS-07 proof"
        )
    )
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--derivation-receipt", required=True, help="Exact sha256:... receipt id")
    parser.add_argument("--proof-out", required=True, help="Digest-only proof path outside repo")
    parser.add_argument("--subject-id", default="local-ocr-replay-operator")
    parser.add_argument(
        "--key",
        nargs=3,
        action="append",
        required=True,
        metavar=("KEY_ID", "VERSION", "FILE"),
        help="Repeat for required evidence keys; put the active key last",
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
            raise PrivateEvidenceError(
                "OCR replay requires explicit --confirm-private-local-case declaration"
            )
        data_root = ensure_data_root(
            Path(args.data_root).expanduser() if args.data_root else None,
            repo_root=ROOT,
        )
        case_key = validate_case_key(args.case)
        case_root = case_dir(case_key, data_root, repo_root=ROOT)
        if not case_root.is_dir():
            raise FileNotFoundError("local case does not exist")
        case_id = CaseManifest.load(case_root).case_id
        authorization = AuthorizationContext(
            subject_id=args.subject_id,
            tenant_id=args.tenant_id,
            roles=("local-ocr-replay-operator",),
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
        proof = verify_environment_bound_ocr_replay(store, args.derivation_receipt)
        proof_target = _outside_repo(Path(args.proof_out), label="OCR replay proof")
        write_ocr_replay_proof(proof, proof_target, repo_root=ROOT)
        print("CASE-OPS-07 OCR REPLAY PASS")
        print("Proof ID:", proof.proof_id)
        print("Derivation receipt:", proof.derivation_receipt_digest)
        print("Observed output ID:", proof.observed_output_id)
        print("Replay class remains:", proof.replay_class)
        print("Independent review claimed: false")
        return 0
    except (OSError, ValueError, RuntimeError, PrivateEvidenceError) as exc:
        print("CASE-OPS-07 OCR REPLAY FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
