from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from core.p3.contracts import content_digest
from scripts.post_hardcore_ph03_closure import (
    MANIFEST_SCHEMA,
    PREDICATE_TYPE,
    SERIALIZATION,
    serialize_closure_manifest,
    validate_closure_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "a" * 40


def _manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": MANIFEST_SCHEMA,
        "serialization": SERIALIZATION,
        "candidate_sha": CANDIDATE,
        "repository": "marcusdd720-ui/lukart-ros",
        "repository_visibility": "public",
        "runtime_identity": {
            "schema": "lukart.runtime-identity.v3",
            "digest": "b" * 64,
            "complete": True,
            "bound_dimensions": ["code_sha", "dependency_lock_digest"],
        },
        "attestation_contract": {
            "predicate_type": PREDICATE_TYPE,
            "provider": "github-actions-sigstore",
            "durable_backend": "public-sigstore-transparency-log",
            "post_merge_main_only": True,
            "short_lived_ci_artifact_days": 30,
            "offline_bundle_verification_supported": True,
        },
        "trust_state": {
            "engineering_state": "ENGINEERING_PASS",
            "review_state": "INDEPENDENT_REVIEW_REQUIRED",
            "independent_certification_claimed": False,
            "release_mutation_requested": False,
        },
    }
    manifest = dict(body)
    manifest["manifest_digest"] = content_digest(body)
    return manifest


def test_ph03_manifest_is_canonical_and_deterministic() -> None:
    manifest = _manifest()
    digest = validate_closure_manifest(manifest, expected_candidate_sha=CANDIDATE)
    first = serialize_closure_manifest(manifest)
    second = serialize_closure_manifest(dict(reversed(list(manifest.items()))))

    assert digest == manifest["manifest_digest"]
    assert first == second
    assert first == first.strip()


def test_ph03_manifest_tamper_fails_closed() -> None:
    manifest = _manifest()
    trust = dict(cast(Mapping[str, object], manifest["trust_state"]))
    trust["review_state"] = "ENGINEERING_PASS"
    manifest["trust_state"] = trust

    with pytest.raises(RuntimeError, match="review boundary"):
        validate_closure_manifest(manifest, expected_candidate_sha=CANDIDATE)


def test_ph03_manifest_digest_mismatch_fails_closed() -> None:
    manifest = _manifest()
    manifest["repository"] = "other/repository"

    with pytest.raises(RuntimeError, match="digest mismatch"):
        validate_closure_manifest(manifest, expected_candidate_sha=CANDIDATE)


def test_ph03_incomplete_runtime_identity_fails_closed() -> None:
    manifest = _manifest()
    runtime = dict(cast(Mapping[str, object], manifest["runtime_identity"]))
    runtime["complete"] = False
    manifest["runtime_identity"] = runtime

    with pytest.raises(RuntimeError, match="runtime identity is incomplete"):
        validate_closure_manifest(manifest, expected_candidate_sha=CANDIDATE)


def test_ph03_standalone_verifier_bootstraps_repo_imports() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "scripts/post_hardcore_ph03_closure.py", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "durable attested closure manifest" in completed.stdout


def test_ph03_policy_is_fail_closed_and_release_safe() -> None:
    policy = json.loads((ROOT / "config/enterprise_v1.json").read_text(encoding="utf-8"))
    ph03 = policy["ph03_durable_attested_evidence"]

    assert ph03["runtime_identity_schema"] == "lukart.runtime-identity.v3"
    assert ph03["public_transparency_log_required"] is True
    assert ph03["attest_only_after_main_merge"] is True
    assert ph03["missing_or_mismatched_material"] == "FAIL"
    assert ph03["release_mutation_requested"] is False
    assert ph03["independent_review_state"] == "INDEPENDENT_REVIEW_REQUIRED"


def test_ph03_runtime_policy_exactly_binds_attestation_actions() -> None:
    policy = json.loads(
        (ROOT / "config/github_actions_runtime_v1.json").read_text(encoding="utf-8")
    )
    actions = policy["approved_actions"]

    assert actions["actions/attest"] == {
        "sha": "1e69f48acb82d1966a394da916b4c1698aa569d6",
        "version": "v4.2.2",
        "runtime": "node24",
    }
    assert actions["actions/download-artifact"] == {
        "sha": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "version": "v8.0.1",
        "runtime": "node24",
    }


def test_ph03_workflow_separates_read_only_validation_from_attestation() -> None:
    workflow = (ROOT / ".github/workflows/enterprise-hardening.yml").read_text(
        encoding="utf-8"
    )

    assert "PH-03 deterministic closure manifest" in workflow
    assert "durable-attestation:" in workflow
    assert "needs: enterprise-gate" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert f"predicate-type: {PREDICATE_TYPE}" in workflow
    assert "build/post-hardcore/ph03-closure-manifest.json" in workflow
    assert "retention-days: 30" in workflow
