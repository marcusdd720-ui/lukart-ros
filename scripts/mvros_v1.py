"""Operational command for running MVROS v1 against a document root."""

from __future__ import annotations

import argparse
from pathlib import Path

from knowledge.pipeline import KnowledgePipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the MVROS v1 knowledge pipeline against a document root."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Directory containing Markdown source documents (default: repository root)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"document root is not a directory: {root}")

    print(f"MVROS v1 root: {root}")
    KnowledgePipeline(root=str(root)).run()
    print("MVROS v1: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
