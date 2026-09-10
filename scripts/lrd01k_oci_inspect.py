"""Inspect a content-addressed OCI Image Layout for LRD-01K."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.cross_environment_replay_v1 import inspect_oci_layout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layout")
    parser.add_argument("--source-bundle-digest", required=True)
    parser.add_argument("--dependency-identity-digest", required=True)
    parser.add_argument("--verifier-digest", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    identity = inspect_oci_layout(
        args.layout,
        source_bundle_digest=args.source_bundle_digest,
        dependency_identity_digest=args.dependency_identity_digest,
        verifier_digest=args.verifier_digest,
    )
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(identity["capsule_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
