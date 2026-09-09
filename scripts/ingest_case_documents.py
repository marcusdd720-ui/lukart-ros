"""Ingest real case source documents into the private local MVROS store."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.case_ingestion import ingest_directory
from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest real case documents into the private local MVROS data root"
    )
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("source", help="Directory containing original case documents")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
    parser.add_argument("--tenant-id", required=True, help="Exact local tenant scope")
    parser.add_argument("--key-id", required=True, help="Evidence encryption key identity")
    parser.add_argument("--key-version", type=int, default=1, help="Evidence key version")
    parser.add_argument(
        "--key-file",
        required=True,
        help="Local file containing exactly 32 raw AES key bytes; never commit it",
    )
    parser.add_argument(
        "--subject-id",
        default="local-case-operator",
        help="Local operator identity recorded only in authorization context",
    )
    args = parser.parse_args()

    try:
        data_root = ensure_data_root(
            Path(args.data_root).expanduser() if args.data_root else None,
            repo_root=ROOT,
        )
        key = validate_case_key(args.case)
        target = case_dir(key, data_root, repo_root=ROOT)
        if not target.is_dir():
            raise FileNotFoundError(
                f"Local case does not exist: {target}. Create it with scripts/new_case.py first."
            )
        provider = LocalFileEvidenceKeyProvider(
            Path(args.key_file),
            key_id=args.key_id,
            key_version=args.key_version,
        )
        authorization = AuthorizationContext(
            subject_id=args.subject_id,
            tenant_id=args.tenant_id,
            roles=("local-case-operator",),
            permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
            case_ids=(key,),
        )
        os.environ["MVROS_DATA_ROOT"] = str(data_root)
        documents = ingest_directory(
            target,
            Path(args.source),
            authorization=authorization,
            key_provider=provider,
            tenant_id=args.tenant_id,
            key_id=args.key_id,
            key_version=args.key_version,
            document_type="real_case",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print("INGESTION FAIL:", exc)
        return 1

    print("INGESTION PASS")
    print("Case:", key)
    print("Data root:", data_root)
    print("Documents:", len(documents))
    for document in documents:
        print(f"  {document.document_id} | {document.evidence_id} | {document.sha256}")
    print("Encrypted evidence store:", target / ".private-evidence")
    print("Compatibility inventory (non-authoritative):", target / "document_inventory.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
