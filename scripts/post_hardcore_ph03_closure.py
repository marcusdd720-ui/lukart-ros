from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from core.p3.contracts import (
    RUNTIME_IDENTITY_V3,
    canonical_json,
    content_digest,
    require_hex_digest,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = "config/enterprise_v1.json"
ACTIONS_RUNTIME_POLICY_PATH = "config/github_actions_runtime_v1.json"
WORKFLOW_PATH = ".github/workflows/enterprise-hardening.yml"
H3_PATH = "build/hardcore/h3-supply-chain-provenance.json"
H5_PATH = "build/hardcore/h5-replay-migration.json"
H10_PATH = "build/hardcore/h10-engineering-evidence-manifest.json"
SBOM_PATH = "build/enterprise/bom.cdx.json"
UV_LOCK_PATH = "uv.lock"
PYLOCK_PATH = "pylock.toml"
PYPROJECT_PATH = "pyproject.toml"
DEFAULT_OUTPUT = "build/post-hardcore/ph03-closure-manifest.json"
MANIFEST_SCHEMA = "lukart.post-hardcore.ph03-closure-manifest.v1"
POLICY_SCHEMA = "lukart.post-hardcore.ph03-durable-evidence.v1"
SERIALIZATION = "lukart.canonical-json.v1"
PREDICATE_TYPE = "https://lukart.dev/attestation/closure-manifest/v1"


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"PH-03 required material is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"PH-03 cannot read JSON material: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"PH-03 JSON material must be an object: {path}")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"PH-03 {label} must be an object")
    return cast(Mapping[str, object], value)


def _string_sequence(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise RuntimeError(f"PH-03 {label} must be an array")
    items = tuple(str(item) for item in value)
    if any(not item for item in items):
        raise RuntimeError(f"PH-03 {label} contains a blank value")
    return items


def _validate_content_digest(
    payload: Mapping[str, object],
    *,
    field: str,
    label: str,
) -> str:
    stored = payload.get(field)
    if not isinstance(stored, str):
        raise RuntimeError(f"PH-03 {label} digest is missing")
    stored = require_hex_digest(stored, field_name=f"ph03_{label}_digest")
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if content_digest(unsigned) != stored:
        raise RuntimeError(f"PH-03 {label} digest mismatch")
    return stored


def _validate_policy(
    policy: Mapping[str, object],
    *,
    repository: str,
    repository_visibility: str,
) -> Mapping[str, object]:
    section = _mapping(
        policy.get("ph03_durable_attested_evidence"),
        label="ph03_durable_attested_evidence",
    )
    required: dict[str, object] = {
        "schema": POLICY_SCHEMA,
        "closure_manifest_schema": MANIFEST_SCHEMA,
        "serialization": SERIALIZATION,
        "runtime_identity_schema": RUNTIME_IDENTITY_V3,
        "exact_candidate_sha_required": True,
        "h10_manifest_required": True,
        "canonical_dependency_lock_required": True,
        "workflow_identity_required": True,
        "github_actions_runtime_policy_required": True,
        "attestation_predicate_type": PREDICATE_TYPE,
        "attestation_provider": "github-actions-sigstore",
        "public_transparency_log_required": True,
        "attest_only_after_main_merge": True,
        "short_lived_ci_artifact_days": 30,
        "release_mutation_requested": False,
        "independent_review_state": "INDEPENDENT_REVIEW_REQUIRED",
        "missing_or_mismatched_material": "FAIL",
    }
    for key, expected in required.items():
        if section.get(key) != expected:
            raise RuntimeError(
                f"PH-03 policy mismatch for {key}: {section.get(key)!r} != {expected!r}"
            )

    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    if h2.get("repository") != repository:
        raise RuntimeError("PH-03 repository identity does not match canonical policy")
    if repository_visibility.strip().lower() != "public":
        raise RuntimeError(
            "PH-03 public transparency-log durability requires a public repository"
        )
    return section


def _validate_h3(
    payload: Mapping[str, object],
    *,
    candidate_sha: str,
    repository: str,
) -> tuple[Mapping[str, object], str]:
    if payload.get("schema") != "lukart.hardcore.h3-provenance.v1":
        raise RuntimeError("PH-03 incompatible H3 provenance schema")
    if payload.get("candidate_sha") != candidate_sha:
        raise RuntimeError("PH-03 mixed candidate SHA in H3 provenance")
    evidence_digest = _validate_content_digest(
        payload,
        field="evidence_digest",
        label="h3_evidence",
    )
    builder = _mapping(payload.get("builder"), label="H3 builder")
    if builder.get("repository") != repository:
        raise RuntimeError("PH-03 H3 builder repository mismatch")
    if builder.get("workflow_path") != WORKFLOW_PATH:
        raise RuntimeError("PH-03 H3 workflow path mismatch")
    return builder, evidence_digest


def _validate_h5(
    payload: Mapping[str, object],
    *,
    candidate_sha: str,
) -> tuple[Mapping[str, object], str]:
    if payload.get("schema") != "lukart.hardcore.h5-replay-migration-evidence.v1":
        raise RuntimeError("PH-03 incompatible H5 replay schema")
    if payload.get("candidate_sha") != candidate_sha:
        raise RuntimeError("PH-03 mixed candidate SHA in H5 replay evidence")
    if payload.get("state") != "CONTROL_PASS":
        raise RuntimeError("PH-03 H5 replay evidence is not CONTROL_PASS")
    evidence_digest = _validate_content_digest(
        payload,
        field="evidence_digest",
        label="h5_evidence",
    )
    runtime = _mapping(payload.get("runtime_identity"), label="H5 runtime identity")
    if runtime.get("current_exact_schema") != RUNTIME_IDENTITY_V3:
        raise RuntimeError("PH-03 requires RuntimeIdentity v3")
    if runtime.get("complete") is not True:
        raise RuntimeError("PH-03 RuntimeIdentity v3 is incomplete")
    digest = runtime.get("digest")
    if not isinstance(digest, str):
        raise RuntimeError("PH-03 RuntimeIdentity v3 digest is missing")
    require_hex_digest(digest, field_name="ph03_runtime_identity_digest")
    dimensions = set(
        _string_sequence(runtime.get("bound_dimensions"), label="runtime bound_dimensions")
    )
    required_dimensions = {
        "code_sha",
        "schema_version",
        "config_digest",
        "corpus_digest",
        "provider_identities",
        "plugin_identities",
        "input_digests",
        "evidence_digests",
        "dependency_lock_digest",
        "python_implementation",
        "python_version",
        "platform_tag",
        "project_version",
        "build_backend",
    }
    missing = sorted(required_dimensions - dimensions)
    if missing:
        raise RuntimeError(f"PH-03 RuntimeIdentity v3 misses dimensions: {missing}")
    return runtime, evidence_digest


def _validate_h10(
    payload: Mapping[str, object],
    *,
    candidate_sha: str,
    expected_config_digest: str,
) -> str:
    if payload.get("schema") != "lukart.hardcore.h10-evidence-manifest.v1":
        raise RuntimeError("PH-03 incompatible H10 evidence manifest schema")
    if payload.get("candidate_sha") != candidate_sha:
        raise RuntimeError("PH-03 mixed candidate SHA in H10 evidence manifest")
    if payload.get("checked_out_head_sha") != candidate_sha:
        raise RuntimeError("PH-03 H10 checked-out SHA mismatch")
    if payload.get("config_digest") != expected_config_digest:
        raise RuntimeError("PH-03 H10 canonical config digest mismatch")
    if payload.get("engineering_state") != "ENGINEERING_PASS":
        raise RuntimeError("PH-03 H10 engineering state is not PASS")
    if payload.get("review_state") != "INDEPENDENT_REVIEW_REQUIRED":
        raise RuntimeError("PH-03 H10 independent-review boundary was weakened")
    if payload.get("independent_certification_claimed") is not False:
        raise RuntimeError("PH-03 H10 contains an invalid certification claim")
    if payload.get("release_mutation_requested") is not False:
        raise RuntimeError("PH-03 cannot attest a release-mutating closure")
    return _validate_content_digest(
        payload,
        field="manifest_digest",
        label="h10_manifest",
    )


def _material_sha256(root: Path, paths: Sequence[str]) -> dict[str, str]:
    return {path: _sha256(root / path) for path in sorted(set(paths))}


def build_closure_manifest(
    candidate_sha: str,
    *,
    repository: str,
    repository_visibility: str,
    root: Path = ROOT,
) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(root), field_name="head_sha", lengths=(40,))
    if head != candidate:
        raise RuntimeError(f"PH-03 exact-SHA mismatch: checked-out HEAD {head} != {candidate}")

    policy = _load_json_object(root / POLICY_PATH)
    ph03_policy = _validate_policy(
        policy,
        repository=repository,
        repository_visibility=repository_visibility,
    )
    enterprise_config_digest = content_digest(policy)
    ph03_policy_digest = content_digest(ph03_policy)

    h3 = _load_json_object(root / H3_PATH)
    h5 = _load_json_object(root / H5_PATH)
    h10 = _load_json_object(root / H10_PATH)
    builder, h3_evidence_digest = _validate_h3(
        h3,
        candidate_sha=candidate,
        repository=repository,
    )
    runtime, h5_evidence_digest = _validate_h5(h5, candidate_sha=candidate)
    h10_manifest_digest = _validate_h10(
        h10,
        candidate_sha=candidate,
        expected_config_digest=enterprise_config_digest,
    )

    workflow_digest = _sha256(root / WORKFLOW_PATH)
    if h3.get("workflow_file_digest") != workflow_digest:
        raise RuntimeError("PH-03 workflow bytes are not bound by H3 provenance")
    if h3.get("pyproject_digest") != _sha256(root / PYPROJECT_PATH):
        raise RuntimeError("PH-03 pyproject bytes are not bound by H3 provenance")
    if h3.get("sbom_file_digest") != _sha256(root / SBOM_PATH):
        raise RuntimeError("PH-03 SBOM bytes are not bound by H3 provenance")

    runtime_digest = runtime.get("digest")
    assert isinstance(runtime_digest, str)
    dependency_identity_digest = h3.get("dependency_identity_digest")
    provenance_digest = h3.get("provenance_digest")
    artifact_manifest_digest = h3.get("artifact_manifest_digest")
    for label, value in {
        "dependency_identity_digest": dependency_identity_digest,
        "provenance_digest": provenance_digest,
        "artifact_manifest_digest": artifact_manifest_digest,
    }.items():
        if not isinstance(value, str):
            raise RuntimeError(f"PH-03 {label} is missing")
        require_hex_digest(value, field_name=f"ph03_{label}")

    enterprise_evidence = _mapping(
        h10.get("enterprise_evidence"),
        label="H10 enterprise_evidence",
    )
    bundle_digest = enterprise_evidence.get("evidence_bundle_digest")
    if not isinstance(bundle_digest, str):
        raise RuntimeError("PH-03 Enterprise evidence bundle digest is missing")
    require_hex_digest(bundle_digest, field_name="ph03_enterprise_bundle_digest")

    material_paths = (
        POLICY_PATH,
        ACTIONS_RUNTIME_POLICY_PATH,
        WORKFLOW_PATH,
        PYPROJECT_PATH,
        UV_LOCK_PATH,
        PYLOCK_PATH,
        H3_PATH,
        H5_PATH,
        H10_PATH,
        SBOM_PATH,
    )
    materials = _material_sha256(root, material_paths)
    uv_lock_digest = materials[UV_LOCK_PATH]

    body: dict[str, object] = {
        "schema": MANIFEST_SCHEMA,
        "serialization": SERIALIZATION,
        "candidate_sha": candidate,
        "repository": repository,
        "repository_visibility": repository_visibility.strip().lower(),
        "code_identity": {"git_sha": candidate},
        "runtime_identity": {
            "schema": RUNTIME_IDENTITY_V3,
            "digest": runtime_digest,
            "complete": True,
            "bound_dimensions": list(
                _string_sequence(
                    runtime.get("bound_dimensions"),
                    label="runtime bound_dimensions",
                )
            ),
        },
        "dependency_identity": {
            "canonical_lock": UV_LOCK_PATH,
            "canonical_lock_sha256": uv_lock_digest,
            "pep751_interop_lock": PYLOCK_PATH,
            "pep751_interop_lock_sha256": materials[PYLOCK_PATH],
            "resolved_dependency_identity_digest": dependency_identity_digest,
        },
        "configuration_identity": {
            "enterprise_config_digest": enterprise_config_digest,
            "ph03_policy_digest": ph03_policy_digest,
            "enterprise_policy_sha256": materials[POLICY_PATH],
            "github_actions_runtime_policy_sha256": materials[
                ACTIONS_RUNTIME_POLICY_PATH
            ],
        },
        "workflow_identity": {
            "path": WORKFLOW_PATH,
            "file_sha256": workflow_digest,
            "workflow_ref": builder.get("workflow_ref"),
            "workflow_sha": builder.get("workflow_sha"),
            "run_id": builder.get("run_id"),
            "run_attempt": builder.get("run_attempt"),
            "runner_os": builder.get("runner_os"),
            "runner_arch": builder.get("runner_arch"),
            "python_version": builder.get("python_version"),
        },
        "evidence_identity": {
            "h3_evidence_digest": h3_evidence_digest,
            "h3_provenance_digest": provenance_digest,
            "h3_artifact_manifest_digest": artifact_manifest_digest,
            "h5_evidence_digest": h5_evidence_digest,
            "h10_manifest_digest": h10_manifest_digest,
            "h10_evidence_set_digest": h10.get("evidence_set_digest"),
            "enterprise_evidence_bundle_digest": bundle_digest,
            "sbom_sha256": materials[SBOM_PATH],
        },
        "material_sha256": materials,
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
    validate_closure_manifest(manifest, expected_candidate_sha=candidate)
    return manifest


def validate_closure_manifest(
    manifest: Mapping[str, object],
    *,
    expected_candidate_sha: str,
) -> str:
    candidate = require_hex_digest(
        expected_candidate_sha,
        field_name="expected_candidate_sha",
        lengths=(40,),
    )
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise RuntimeError("PH-03 closure manifest schema mismatch")
    if manifest.get("serialization") != SERIALIZATION:
        raise RuntimeError("PH-03 closure manifest serialization mismatch")
    if manifest.get("candidate_sha") != candidate:
        raise RuntimeError("PH-03 closure manifest candidate SHA mismatch")
    if manifest.get("repository_visibility") != "public":
        raise RuntimeError("PH-03 durable public attestation requires public visibility")
    runtime = _mapping(manifest.get("runtime_identity"), label="runtime_identity")
    if runtime.get("schema") != RUNTIME_IDENTITY_V3 or runtime.get("complete") is not True:
        raise RuntimeError("PH-03 closure manifest runtime identity is incomplete")
    require_hex_digest(
        str(runtime.get("digest", "")),
        field_name="ph03_manifest_runtime_identity_digest",
    )
    trust = _mapping(manifest.get("trust_state"), label="trust_state")
    if trust.get("engineering_state") != "ENGINEERING_PASS":
        raise RuntimeError("PH-03 closure manifest is not ENGINEERING_PASS")
    if trust.get("review_state") != "INDEPENDENT_REVIEW_REQUIRED":
        raise RuntimeError("PH-03 closure manifest review boundary mismatch")
    if trust.get("independent_certification_claimed") is not False:
        raise RuntimeError("PH-03 closure manifest makes an invalid certification claim")
    if trust.get("release_mutation_requested") is not False:
        raise RuntimeError("PH-03 closure manifest requests release mutation")
    attestation = _mapping(
        manifest.get("attestation_contract"),
        label="attestation_contract",
    )
    if attestation.get("predicate_type") != PREDICATE_TYPE:
        raise RuntimeError("PH-03 attestation predicate type mismatch")
    if attestation.get("post_merge_main_only") is not True:
        raise RuntimeError("PH-03 attestation must be post-merge main only")

    stored = manifest.get("manifest_digest")
    if not isinstance(stored, str):
        raise RuntimeError("PH-03 closure manifest digest is missing")
    stored = require_hex_digest(stored, field_name="ph03_manifest_digest")
    unsigned = dict(manifest)
    unsigned.pop("manifest_digest", None)
    if content_digest(unsigned) != stored:
        raise RuntimeError("PH-03 closure manifest digest mismatch")
    return stored


def serialize_closure_manifest(manifest: Mapping[str, object]) -> bytes:
    return canonical_json(manifest).encode("utf-8")


def verify_existing_manifest(path: Path, *, expected_candidate_sha: str) -> str:
    payload = _load_json_object(path)
    digest = validate_closure_manifest(
        payload,
        expected_candidate_sha=expected_candidate_sha,
    )
    canonical_bytes = serialize_closure_manifest(payload)
    if path.read_bytes() != canonical_bytes:
        raise RuntimeError("PH-03 closure manifest is not canonically serialized")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify PH-03 durable attested closure manifest"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--repository", default="marcusdd720-ui/lukart-ros")
    parser.add_argument("--repository-visibility", default="public")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-existing")
    args = parser.parse_args()

    if args.verify_existing:
        digest = verify_existing_manifest(
            Path(args.verify_existing),
            expected_candidate_sha=args.candidate_sha,
        )
        print("PH03_CLOSURE_MANIFEST_VERIFY=PASS")
        print(f"PH03_MANIFEST_DIGEST={digest}")
        return 0

    manifest = build_closure_manifest(
        args.candidate_sha,
        repository=args.repository,
        repository_visibility=args.repository_visibility,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(serialize_closure_manifest(manifest))
    digest = verify_existing_manifest(
        output,
        expected_candidate_sha=args.candidate_sha,
    )
    file_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    print("PH03_CLOSURE_MANIFEST=PASS")
    print(f"PH03_CANDIDATE_SHA={manifest['candidate_sha']}")
    print(f"PH03_MANIFEST_DIGEST={digest}")
    print(f"PH03_MANIFEST_SHA256={file_sha256}")
    print(f"PH03_MANIFEST_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
