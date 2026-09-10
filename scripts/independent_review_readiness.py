"""CLI for building and verifying the IRR-01/v1 reviewer handoff package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.independent_review_readiness_v1 import (  # noqa: E402
    ReviewPackageResultV1,
    build_review_package_v1,
    verify_review_package_v1,
)


def _result_payload(result: ReviewPackageResultV1) -> dict[str, object]:
    return {
        "schema": "lukart.independent-review-readiness-cli.v1",
        "readiness_status": result.readiness_status,
        "independent_review_status": result.independent_review_status,
        "source_commit_sha": result.source_commit_sha,
        "package_sha256": result.package_sha256,
        "file_count": result.file_count,
        "total_payload_bytes": result.total_payload_bytes,
        "package_path": str(result.package_path),
        "sha256_path": str(result.sha256_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="IRR-01 independent-review readiness package")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--repo-root", default=".")
    build.add_argument("--commit", required=True)
    build.add_argument("--output-dir", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--package", required=True)

    args = parser.parse_args()
    if args.command == "build":
        result = build_review_package_v1(
            repo_root=Path(args.repo_root),
            commit_sha=args.commit,
            output_dir=Path(args.output_dir),
        )
    else:
        result = verify_review_package_v1(Path(args.package))
    print(json.dumps(_result_payload(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
