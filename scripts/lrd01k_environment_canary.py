"""Generate deterministic-identity LRD-01K synthetic cross-environment canary evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core.cross_environment_replay_v1 import (
    build_environment_profile,
    build_observed_environment_receipt,
    capture_environment_snapshot,
    digest_value,
    sha256_file,
)


def _h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lock", default="pylock.toml")
    args = parser.parse_args()
    verifier = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cross_environment_replay_verifier_v1.py"
    )
    verifier_digest = sha256_file(verifier)
    policy_digest = digest_value(
        {
            "schema": "lukart.lrd01k-environment-policy.v1",
            "network": "DENY",
            "write_authority": "NONE",
        }
    )
    snapshot = capture_environment_snapshot()
    installed_digest = str(snapshot["installed_artifact_inventory_digest"])
    bundle_digest = _h("lrd01k-synthetic-lrd01i-bundle-v1")
    profile = build_environment_profile(
        name=args.name,
        observed=snapshot,
        dependency_lock_digest=sha256_file(args.lock),
        physical_dependency_artifact_identities=[installed_digest],
        canonicalization_profile_digest=_h("core.p3.contracts:canonical_json"),
        migration_registry_digest=_h("lrd01j-migration-registry-binding"),
        crypto_profile_digest=_h("lrd01j-crypto-profile-binding"),
        lrd01i_bundle_digest=bundle_digest,
        replay_verifier_digest=verifier_digest,
        environment_policy_digest=policy_digest,
    )
    observed = build_observed_environment_receipt(
        snapshot,
        declared_profile_digest=str(profile["profile_digest"]),
        verifier_digest=verifier_digest,
        environment_policy_digest=policy_digest,
    )
    # The single-environment canary intentionally emits provenance objects only. Aggregate
    # plan/report construction occurs after matrix collection so partial matrices fail closed.
    payload = {"profile": profile, "observed": observed, "bindings": {
        "lrd01i_bundle_digest": bundle_digest,
        "ssc02_manifest_digest": _h("ssc02-synthetic-canary-v1"),
        "replay_policy_digest": _h("lrd01k-replay-policy-v1"),
        "migration_registry_digest": profile["migration_registry_digest"],
        "canonicalization_profile_digest": profile["canonicalization_profile_digest"],
        "crypto_profile_digest": profile["crypto_profile_digest"],
        "semantic_result_identity": _h("lrd01k-semantic-canary-v1"),
        "invariant_report_identity": _h("lrd01k-invariants-canary-v1"),
        "verifier_digest": verifier_digest,
    }}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(profile["profile_digest"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
