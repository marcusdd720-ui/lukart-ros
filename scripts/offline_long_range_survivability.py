"""Operator entry point for LRD-01I offline long-range survivability bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from core.artifact_escrow_v1 import ArtifactEscrowManifestV1, FileSystemEscrowBackendV1
from core.long_range_replay_v1 import LongRangeReplayManifestV1, ReplayCapsuleV1
from core.offline_long_range_survivability_v1 import (
    OfflineLongRangeSurvivabilityError,
    build_offline_survivability_bundle,
    verify_offline_survivability_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


class OfflineSurvivabilityOperatorError(ValueError):
    """Fail-closed operator input error."""


def _outside_repo(path: Path, *, field_name: str, must_exist: bool) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise OfflineSurvivabilityOperatorError(f"{field_name} must not be a symlink")
    resolved = expanded.resolve(strict=must_exist)
    if resolved == ROOT or ROOT in resolved.parents:
        raise OfflineSurvivabilityOperatorError(
            f"{field_name} must remain outside the public repository tree"
        )
    return resolved


def _json_object(path: Path, *, field_name: str) -> dict[str, object]:
    resolved = _outside_repo(path, field_name=field_name, must_exist=True)
    if not resolved.is_file():
        raise OfflineSurvivabilityOperatorError(f"{field_name} must be a regular file")
    try:
        decoded: object = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineSurvivabilityOperatorError(f"cannot read {field_name}") from exc
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise OfflineSurvivabilityOperatorError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _build(args: argparse.Namespace) -> int:
    lrd = LongRangeReplayManifestV1.from_dict(
        _json_object(Path(args.lrd_manifest), field_name="LRD manifest")
    )
    capsule = ReplayCapsuleV1.from_dict(
        _json_object(Path(args.replay_capsule), field_name="replay capsule")
    )
    escrow = ArtifactEscrowManifestV1.from_dict(
        _json_object(Path(args.escrow_manifest), field_name="escrow manifest")
    )
    escrow_root = _outside_repo(Path(args.escrow_root), field_name="escrow root", must_exist=True)
    continuity = _outside_repo(
        Path(args.continuity_bundle),
        field_name="SSC-02 continuity bundle",
        must_exist=True,
    )
    output = _outside_repo(Path(args.output), field_name="survivability output", must_exist=False)
    manifest = build_offline_survivability_bundle(
        output_root=output,
        lrd_manifest=lrd,
        replay_capsule=capsule,
        escrow_manifest=escrow,
        escrow_backend=FileSystemEscrowBackendV1(escrow_root, create=False),
        continuity_bundle_root=continuity,
    )
    print("LRD-01I OFFLINE SURVIVABILITY BUNDLE BUILT")
    print("Bundle digest:", manifest["bundle_digest"])
    print("Output:", output)
    print("Physical interpreter preserved: false")
    return 0


def _verify(args: argparse.Namespace) -> int:
    bundle = _outside_repo(Path(args.bundle), field_name="survivability bundle", must_exist=True)
    digest = verify_offline_survivability_bundle(
        bundle,
        expected_digest=args.expected_digest,
    )
    print("LRD-01I OFFLINE SURVIVABILITY VERIFY PASS")
    print("Bundle digest:", digest)
    print("Provider access required: false")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LRD-01I offline survivability operator")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--lrd-manifest", required=True)
    build.add_argument("--replay-capsule", required=True)
    build.add_argument("--escrow-manifest", required=True)
    build.add_argument("--escrow-root", required=True)
    build.add_argument("--continuity-bundle", required=True)
    build.add_argument("--output", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--expected-digest", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "build":
            return _build(args)
        return _verify(args)
    except (OfflineLongRangeSurvivabilityError, OfflineSurvivabilityOperatorError) as exc:
        raise SystemExit(f"LRD-01I rejected: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
