"""Operator CLI for CASE-OPS-08 derivation migration-readiness inventory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_derivation_migration_v1 import (
    build_derivation_migration_readiness,
    write_migration_readiness_report,
)
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_recovery_v1 import RecoveredEvidenceKeyProvider
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore, digest_hex
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


def _read_candidate(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("config candidate must be a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("config candidate must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("config candidate must be a JSON mapping")
    return value


def _parse_candidates(values: list[list[str]] | None) -> dict[str, dict[str, object]]:
    candidates: dict[str, dict[str, object]] = {}
    for receipt_digest, raw_path in values or []:
        digest_hex(receipt_digest)
        if receipt_digest in candidates:
            raise ValueError("duplicate config candidate for one derivation receipt")
        candidates[receipt_digest] = _read_candidate(Path(raw_path).expanduser())
    return candidates


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify CASE-OPS private derivations and emit a content-addressed migration-readiness "
            "report without rewriting historical receipts"
        )
    )
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--report-out", required=True, help="Private report path outside repo")
    parser.add_argument("--subject-id", default="local-derivation-migration-operator")
    parser.add_argument(
        "--key",
        nargs=3,
        action="append",
        required=True,
        metavar=("KEY_ID", "VERSION", "FILE"),
        help="Repeat for required evidence keys; put the active key last",
    )
    parser.add_argument(
        "--config-candidate",
        nargs=2,
        action="append",
        metavar=("DERIVATION_RECEIPT_DIGEST", "JSON_FILE"),
        help="Optional exact UTF-8 v1 config candidate for a historical receipt digest",
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
                "migration inventory requires explicit --confirm-private-local-case declaration"
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
            roles=("local-derivation-migration-operator",),
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
        candidates = _parse_candidates(args.config_candidate)
        report = build_derivation_migration_readiness(store, config_candidates=candidates)
        report_target = _outside_repo(Path(args.report_out), label="migration report")
        write_migration_readiness_report(report, report_target, repo_root=ROOT)
        action_required = sum(entry.migration_action != "NONE" for entry in report.entries)
        print("CASE-OPS-08 MIGRATION READINESS", report.overall_status)
        print("Report ID:", report.report_id)
        print("Policy ID:", report.policy_id)
        print("Derivations:", len(report.entries))
        print("Actions required:", action_required)
        print("Historical receipts mutated: false")
        print("CCL write authority: false")
        print("Independent review claimed: false")
        return 0 if report.overall_status == "READY" else 2
    except (OSError, ValueError, RuntimeError) as exc:
        print("CASE-OPS-08 MIGRATION READINESS FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
