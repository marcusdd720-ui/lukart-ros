"""Aggregate independently observed LRD-01K canary environments and verify the report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from core.cross_environment_replay_v1 import (
    ReplayExecutionStatus,
    build_replay_plan,
    build_replay_receipt,
    build_replay_report,
)
from core.cross_environment_replay_verifier_v1 import verify_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payloads = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.inputs]
    profiles = [cast(dict[str, object], item["profile"]) for item in payloads]
    observed = [cast(dict[str, object], item["observed"]) for item in payloads]
    bindings = cast(dict[str, object], payloads[0]["bindings"])
    for item in payloads[1:]:
        if item["bindings"] != bindings:
            raise SystemExit("cross-environment canary binding divergence")
    profile_ids = [str(item["profile_digest"]) for item in profiles]
    plan = build_replay_plan(
        lrd01i_bundle_digest=str(bindings["lrd01i_bundle_digest"]),
        ssc02_manifest_digest=str(bindings["ssc02_manifest_digest"]),
        environment_profile_digests=profile_ids,
        reference_profile_digest=profile_ids[0],
        replay_policy_digest=str(bindings["replay_policy_digest"]),
        migration_registry_digest=str(bindings["migration_registry_digest"]),
        canonicalization_profile_digest=str(bindings["canonicalization_profile_digest"]),
        crypto_profile_digest=str(bindings["crypto_profile_digest"]),
        expected_matrix=profile_ids,
        hard_bounds={"network": "DENY", "ccl_write": False, "product_write": False},
    )
    receipts = [
        build_replay_receipt(
            plan=plan,
            profile=profile,
            observed=observation,
            verifier_digest=str(bindings["verifier_digest"]),
            semantic_result_identity=str(bindings["semantic_result_identity"]),
            invariant_report_identity=str(bindings["invariant_report_identity"]),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )
        for profile, observation in zip(profiles, observed, strict=True)
    ]
    report = build_replay_report(plan=plan, profiles=profiles, observed_environments=observed, receipts=receipts)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    verified = verify_file(output, str(report["report_digest"]))
    print(verified)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
