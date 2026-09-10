"""Generate deterministic-identity LRD-01K synthetic cross-environment canary evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from core.cross_environment_replay_v1 import (
    build_environment_profile,
    build_observed_environment_receipt,
    capture_environment_snapshot,
    digest_value,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _repository_blob_sha256(path: str | Path) -> str:
    candidate = Path(path)
    absolute = candidate if candidate.is_absolute() else _REPOSITORY_ROOT / candidate
    try:
        relative = absolute.resolve(strict=False).relative_to(_REPOSITORY_ROOT).as_posix()
    except ValueError as exc:
        raise SystemExit("LRD-01K source identity path must be inside the repository") from exc
    try:
        content = subprocess.check_output(
            ["git", "-C", str(_REPOSITORY_ROOT), "show", f"HEAD:{relative}"]
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot read exact repository blob identity for {relative}") from exc
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lock", default="pylock.toml")
    args = parser.parse_args()
    verifier = (
        _REPOSITORY_ROOT
        / "core"
        / "cross_environment_replay_verifier_v1.py"
    )
    verifier_digest = _repository_blob_sha256(verifier)
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
        dependency_lock_digest=_repository_blob_sha256(args.lock),
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
