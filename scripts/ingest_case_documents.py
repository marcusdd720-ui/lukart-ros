"""Ingest real case source documents into the private local MVROS store."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.case_ingestion import ingest_directory
from core.local_case_store import case_dir, ensure_data_root, validate_case_key

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest real case documents into the private local MVROS data root"
    )
    parser.add_argument("case", help="Private local case key")
    parser.add_argument("source", help="Directory containing original case documents")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
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
        os.environ["MVROS_DATA_ROOT"] = str(data_root)
        documents = ingest_directory(target, Path(args.source), document_type="real_case")
    except (OSError, ValueError, RuntimeError) as exc:
        print("INGESTION FAIL:", exc)
        return 1

    print("INGESTION PASS")
    print("Case:", key)
    print("Data root:", data_root)
    print("Documents:", len(documents))
    for document in documents:
        print(f"  {document.document_id} | {document.source_name} | {document.sha256}")
    print("Originals:", target / "original")
    print("Extracted:", target / "extracted")
    print("Markdown:", target / "markdown")
    print("Inventory:", target / "document_inventory.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
