from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from core.p3.contracts import content_digest, require_hex_digest
from core.p3.scale import (
    ScaleProfile,
    StructuralScaleBudget,
    certify_profile_structure,
    measure_scale_profile,
    repeated_measurement_digest,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _profiles() -> tuple[ScaleProfile, ...]:
    return (
        ScaleProfile("small", 64, 64, 8, 2),
        ScaleProfile("medium", 256, 256, 16, 4),
        ScaleProfile("large", 1024, 1024, 64, 8),
        ScaleProfile("stress", 4096, 4096, 128, 8),
    )


def build_h8_evidence(candidate_sha: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if candidate != head:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    h8 = document.get("h8_scale_concurrency")
    if not isinstance(h8, dict):
        raise RuntimeError("H8 scale/concurrency policy is missing")
    required = {
        "structural_budget_schema": "lukart.structural-scale-budget.v1",
        "required_profiles": ["small", "medium", "large", "stress"],
        "deterministic_work_identity_required": True,
        "concurrency_invariant_work_identity": True,
        "runtime_memory_are_measured_evidence": True,
        "wall_clock_is_not_sole_trust_gate": True,
        "resource_budget_breach": "FAIL",
        "nondeterministic_work_identity": "FAIL",
    }
    for key, expected in required.items():
        if h8.get(key) != expected:
            raise RuntimeError(f"H8 policy mismatch for {key}: {h8.get(key)!r} != {expected!r}")

    integer_fields = (
        "max_evidence_count",
        "max_graph_nodes",
        "max_replay_count",
        "max_concurrency",
        "max_blast_radius_size",
    )
    integer_values: dict[str, int] = {}
    for field in integer_fields:
        value = h8.get(field)
        if not isinstance(value, int) or value < 1:
            raise RuntimeError(f"H8 {field} must be a positive integer")
        integer_values[field] = value

    budget = StructuralScaleBudget(**integer_values)
    measurements: list[dict[str, object]] = []
    work_digests: dict[str, str] = {}
    for profile in _profiles():
        structural = certify_profile_structure(profile, budget)
        if not structural.passed:
            raise RuntimeError(f"H8 structural budget failed for {profile.name}: {structural.failures}")
        measurement = measure_scale_profile(profile)
        post_measurement = certify_profile_structure(
            profile,
            budget,
            blast_radius_size=measurement.blast_radius_size,
        )
        if not post_measurement.passed:
            raise RuntimeError(
                f"H8 measured structural identity failed for {profile.name}: "
                f"{post_measurement.failures}"
            )
        repeats = repeated_measurement_digest(
            lambda profile=profile: measure_scale_profile(profile),
            repetitions=2,
        )
        if len(set(repeats)) != 1 or repeats[0] != measurement.work_digest:
            raise RuntimeError(f"H8 nondeterministic work identity for {profile.name}")
        work_digests[profile.name] = measurement.work_digest
        measurements.append(
            {
                "profile": profile.canonical_dict(),
                "profile_digest": profile.digest(),
                "structural_certification": {
                    "passed": structural.passed,
                    "failures": list(structural.failures),
                    "budget_digest": structural.budget_digest,
                },
                "measurement": {
                    "duration_seconds": measurement.duration_seconds,
                    "peak_memory_bytes": measurement.peak_memory_bytes,
                    "cache_hit_ratio": measurement.cache_hit_ratio,
                    "blast_radius_size": measurement.blast_radius_size,
                    "work_digest": measurement.work_digest,
                },
                "repeat_work_digests": list(repeats),
            }
        )

    serial = ScaleProfile("concurrency-invariant", 256, 256, 64, 1)
    parallel = ScaleProfile("concurrency-invariant", 256, 256, 64, budget.max_concurrency)
    serial_result = measure_scale_profile(serial)
    parallel_result = measure_scale_profile(parallel)
    if serial_result.work_digest != parallel_result.work_digest:
        raise RuntimeError("H8 work identity changed with concurrency level")

    excessive_concurrency = ScaleProfile(
        "concurrency-breach",
        64,
        64,
        8,
        budget.max_concurrency + 1,
    )
    breach = certify_profile_structure(excessive_concurrency, budget)
    if breach.passed or "concurrency" not in breach.failures:
        raise RuntimeError("H8 concurrency budget breach was not rejected")

    evidence_body: dict[str, object] = {
        "schema": "lukart.hardcore.h8-scale-concurrency-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "policy_digest": content_digest(h8),
        "budget": budget.canonical_dict(),
        "budget_digest": budget.digest(),
        "profiles": measurements,
        "work_digests": work_digests,
        "concurrency_invariance": {
            "serial": serial_result.work_digest,
            "parallel": parallel_result.work_digest,
            "same": serial_result.work_digest == parallel_result.work_digest,
        },
        "adversarial_budget_breach": {
            "passed": breach.passed,
            "failures": list(breach.failures),
        },
        "state": "CONTROL_PASS",
    }
    evidence_body["evidence_digest"] = content_digest(evidence_body)
    return evidence_body


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate H8 scale, concurrency and resource budgets")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="build/hardcore/h8-scale-concurrency.json")
    args = parser.parse_args()

    evidence = build_h8_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H8_SCALE_CONCURRENCY=PASS")
    print(f"H8_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H8_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H8_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
