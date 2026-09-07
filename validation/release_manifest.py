"""Content-addressed release manifest for future immutable publications."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from core.p3.contracts import canonical_json, content_digest

RELEASE_MANIFEST_SCHEMA = "lukart.release-manifest.v1"
SERIALIZATION = "lukart.canonical-json.v1"
_STABLE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
_HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ReleaseManifestError(RuntimeError):
    """Raised when release material cannot be bound deterministically."""


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise ReleaseManifestError(f"required release material is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_manifest(
    *,
    candidate_sha: str,
    version: str,
    tag: str,
    dist_dir: Path,
    closure_manifest: Path,
    sbom: Path,
) -> dict[str, object]:
    candidate_sha = candidate_sha.strip().lower()
    version = version.strip()
    tag = tag.strip()
    if not _HEX_SHA.fullmatch(candidate_sha):
        raise ReleaseManifestError("candidate_sha must be an exact 40-hex SHA")
    if not _STABLE_VERSION.fullmatch(version):
        raise ReleaseManifestError("release version must be stable X.Y.Z")
    if tag != f"v{version}":
        raise ReleaseManifestError("release tag must be derived from the canonical version")

    try:
        closure_payload = json.loads(closure_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseManifestError("PH-03 closure manifest is unreadable") from exc
    if not isinstance(closure_payload, dict):
        raise ReleaseManifestError("PH-03 closure manifest must be an object")
    if closure_payload.get("candidate_sha") != candidate_sha:
        raise ReleaseManifestError("PH-03 closure manifest is bound to another SHA")

    wheels = sorted(dist_dir.glob("*.whl"))
    checksum_file = dist_dir / "SHA256SUMS"
    if len(wheels) != 1:
        raise ReleaseManifestError("release build must contain exactly one wheel")
    if not checksum_file.is_file():
        raise ReleaseManifestError("release SHA256SUMS file is missing")

    assets = [
        {"name": path.name, "sha256": _sha256(path)}
        for path in sorted([*wheels, checksum_file], key=lambda item: item.name)
    ]
    body: dict[str, object] = {
        "schema": RELEASE_MANIFEST_SCHEMA,
        "serialization": SERIALIZATION,
        "candidate_sha": candidate_sha,
        "version": version,
        "tag": tag,
        "immutability": {
            "publish_once": True,
            "repository_immutable_releases_required": True,
        },
        "materials": {
            "ph03_closure_manifest": {
                "path": "build/post-hardcore/ph03-closure-manifest.json",
                "sha256": _sha256(closure_manifest),
            },
            "sbom": {
                "path": "build/enterprise/bom.cdx.json",
                "sha256": _sha256(sbom),
            },
        },
        "assets": assets,
        "trust_state": {
            "engineering_state": "ENGINEERING_PASS",
            "independent_review_state": "INDEPENDENT_REVIEW_REQUIRED",
            "independent_certification_claimed": False,
        },
    }
    manifest = dict(body)
    manifest["manifest_digest"] = content_digest(body)
    return manifest


def serialize_release_manifest(manifest: dict[str, object]) -> str:
    return canonical_json(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical future-release manifest")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument(
        "--closure-manifest", default="build/post-hardcore/ph03-closure-manifest.json"
    )
    parser.add_argument("--sbom", default="build/enterprise/bom.cdx.json")
    parser.add_argument("--output", default="build/release/release-manifest.json")
    args = parser.parse_args()

    manifest = build_release_manifest(
        candidate_sha=args.candidate_sha,
        version=args.version,
        tag=args.tag,
        dist_dir=Path(args.dist_dir),
        closure_manifest=Path(args.closure_manifest),
        sbom=Path(args.sbom),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialize_release_manifest(manifest) + "\n", encoding="utf-8")
    print(f"RELEASE_MANIFEST_DIGEST={manifest['manifest_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
