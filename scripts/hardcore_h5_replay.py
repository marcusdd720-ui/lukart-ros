from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from core.p3 import (
    CaseMigrationRegistry,
    MigrationStep,
    P3ContractError,
    ReplayRelation,
    RuntimeIdentity,
    VersionedCase,
    content_digest,
    require_hex_digest,
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


def _identity(candidate_sha: str, *, schema_version: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=candidate_sha,
        schema_version=schema_version,
        config_digest=content_digest({"config": "h5"}),
        corpus_digest=content_digest({"corpus": "h5"}),
        provider_identities=("synthetic-provider@1.0.0",),
        plugin_identities=("synthetic-plugin@1.0.0",),
        input_digests=(content_digest({"input": "h5"}),),
        evidence_digests=(content_digest({"evidence": "h5"}),),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
    )


def _expect_contract_error(action: object, marker: str) -> dict[str, object]:
    if not callable(action):
        raise RuntimeError("H5 adversarial action must be callable")
    try:
        action()
    except P3ContractError as exc:
        if marker not in str(exc):
            raise RuntimeError(f"unexpected H5 denial reason: {exc}") from exc
        return {"denied": True, "reason_class": marker}
    raise RuntimeError(f"H5 boundary unexpectedly accepted condition: {marker}")


def build_h5_evidence(candidate_sha: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if head != candidate:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    policy_document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    h5 = policy_document.get("h5_replay_migration")
    if not isinstance(h5, dict):
        raise RuntimeError("H5 replay/migration policy is missing")
    required_contract = {
        "runtime_identity_schema": "lukart.runtime-identity.v2",
        "complete_identity_required_for_identical": True,
        "provider_plugin_versions_required": True,
        "input_evidence_digests_required": True,
        "explicit_cross_version_migration_required": True,
        "unknown_migration_path": "FAIL",
        "ambiguous_migration_path": "FAIL",
        "semantic_divergence_visible": True,
    }
    for key, expected in required_contract.items():
        if h5.get(key) != expected:
            raise RuntimeError(f"H5 policy mismatch for {key}: {h5.get(key)!r} != {expected!r}")

    registry = CaseMigrationRegistry()
    exact = _identity(candidate, schema_version="v1")
    identical = registry.compare_replay(exact, exact)
    if identical.relation is not ReplayRelation.IDENTICAL or not exact.complete_for_replay:
        raise RuntimeError("H5 complete exact identity did not classify as IDENTICAL")

    incomplete = RuntimeIdentity(
        code_sha=candidate,
        schema_version="v1",
        config_digest=content_digest({"config": "h5"}),
        corpus_digest=content_digest({"corpus": "h5"}),
    )
    incomplete_result = registry.compare_replay(incomplete, incomplete)
    if incomplete_result.relation is not ReplayRelation.INCOMPLETE:
        raise RuntimeError("H5 partial identity was incorrectly promoted to IDENTICAL")

    registry.register(MigrationStep("v1", "v2", lambda payload: {**payload, "schema": "v2"}))
    source = VersionedCase.build(case_id="H5-SYNTHETIC", schema_version="v1", payload={"x": 1})
    migration = registry.migrate(source, "v2")
    cross_version = registry.compare_replay(
        exact,
        _identity(candidate, schema_version="v2"),
        migration_report=migration,
    )
    if cross_version.relation is not ReplayRelation.CROSS_VERSION_COMPARABLE:
        raise RuntimeError("H5 explicit migration was not classified as cross-version comparable")
    if cross_version.semantic_divergence is not True or cross_version.unresolved:
        raise RuntimeError("H5 semantic divergence was hidden or left unresolved")

    unknown_registry = CaseMigrationRegistry()
    unknown_denial = _expect_contract_error(
        lambda: unknown_registry.compare_replay(
            _identity(candidate, schema_version="v1"),
            _identity(candidate, schema_version="v9"),
        ),
        "no migration path",
    )

    ambiguous_registry = CaseMigrationRegistry()
    ambiguous_registry.register(MigrationStep("v1", "v2", lambda payload: dict(payload)))
    ambiguous_registry.register(MigrationStep("v2", "v3", lambda payload: dict(payload)))
    ambiguous_registry.register(MigrationStep("v1", "v3", lambda payload: dict(payload)))
    ambiguous_denial = _expect_contract_error(
        lambda: ambiguous_registry.path("v1", "v3"),
        "ambiguous migration path",
    )

    evidence_body: dict[str, object] = {
        "schema": "lukart.hardcore.h5-replay-migration-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "policy_digest": content_digest(h5),
        "runtime_identity": {
            "schema": exact.identity_schema,
            "digest": exact.digest(),
            "complete": exact.complete_for_replay,
            "bound_dimensions": [
                "code_sha",
                "schema_version",
                "config_digest",
                "corpus_digest",
                "provider_identities",
                "plugin_identities",
                "input_digests",
                "evidence_digests",
            ],
        },
        "replay_relations": {
            "exact": identical.relation.value,
            "partial": incomplete_result.relation.value,
            "cross_version": cross_version.relation.value,
        },
        "migration": {
            "path": list(migration.path),
            "path_digest": migration.path_digest,
            "semantic_divergence": cross_version.semantic_divergence,
        },
        "adversarial_denials": {
            "unknown_path": unknown_denial,
            "ambiguous_path": ambiguous_denial,
        },
        "state": "CONTROL_PASS",
    }
    evidence_body["evidence_digest"] = content_digest(evidence_body)
    return evidence_body


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate H5 deterministic replay identity and migration closure")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="build/hardcore/h5-replay-migration.json")
    args = parser.parse_args()

    evidence = build_h5_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H5_REPLAY_MIGRATION=PASS")
    print(f"H5_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H5_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H5_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
