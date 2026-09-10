"""CLI for IRH-01 handoff creation and external review evidence verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.independent_review_handoff_v1 import (
    build_handoff_from_irr_package_v1,
    load_handoff_v1,
    load_review_evidence_v1,
    load_trust_set_v1,
    verify_external_review_evidence_v1,
)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _create_handoff(args: argparse.Namespace) -> int:
    handoff = build_handoff_from_irr_package_v1(Path(args.package))
    output = Path(args.output)
    _write_json(output, handoff.canonical_dict())
    print(f"IRH01_HANDOFF_IDENTITY={handoff.handoff_identity}")
    print(f"IRH01_IRR_SOURCE_SHA={handoff.irr_source_commit_sha}")
    print(f"IRH01_IRR_PACKAGE_SHA256={handoff.irr_package_sha256}")
    print(f"IRH01_EXTERNAL_REVIEW_STATUS={handoff.external_review_status}")
    print(f"IRH01_INDEPENDENT_REVIEW_STATUS={handoff.independent_review_status}")
    print("IRH01_AUTOMATION_CAN_CREATE_REVIEW=false")
    print("IRH01_AUTOMATION_CAN_CERTIFY=false")
    return 0


def _verify(args: argparse.Namespace) -> int:
    handoff = load_handoff_v1(Path(args.handoff))
    evidence = load_review_evidence_v1(Path(args.submission))
    trust_set = load_trust_set_v1(Path(args.trust_set))
    result = verify_external_review_evidence_v1(
        expected_handoff=handoff,
        evidence=evidence,
        review_artifact_path=Path(args.artifact),
        trust_set=trust_set,
        expected_trust_set_digest=args.expected_trust_set_digest,
        now=args.now,
    )
    print(json.dumps(result.canonical_dict(), ensure_ascii=True, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IRH-01 independent-review handoff/provenance verifier"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser(
        "create-handoff",
        help="verify an IRR-01 package and create its immutable review handoff",
    )
    create.add_argument("--package", required=True)
    create.add_argument("--output", required=True)
    create.set_defaults(func=_create_handoff)

    verify = subparsers.add_parser(
        "verify",
        help="verify externally returned review evidence under a pinned trust set",
    )
    verify.add_argument("--handoff", required=True)
    verify.add_argument("--submission", required=True)
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--trust-set", required=True)
    verify.add_argument("--expected-trust-set-digest", required=True)
    verify.add_argument("--now", required=True, type=int)
    verify.set_defaults(func=_verify)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
