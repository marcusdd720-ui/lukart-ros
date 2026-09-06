from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
ENTERPRISE_EVIDENCE_PATH = "build/enterprise/enterprise-engineering-evidence.json"


@dataclass(frozen=True, slots=True)
class StageSpec:
    stage: str
    path: str
    schema: str
    policy_key: str | None = None
    require_control_pass: bool = True
    require_internal_digest: bool = False


STAGE_SPECS: dict[str, StageSpec] = {
    "H1": StageSpec(
        "H1",
        "build/hardcore/h1-baseline-evidence.json",
        "lukart.hardcore-h1-evidence.v2",
    ),
    "H2": StageSpec(
        "H2",
        "build/hardcore/h2-repository-policy-evidence.json",
        "lukart.hardcore-h2-evidence.v1",
    ),
    "H3": StageSpec(
        "H3",
        "build/hardcore/h3-supply-chain-provenance.json",
        "lukart.hardcore.h3-provenance.v1",
        require_control_pass=False,
        require_internal_digest=True,
    ),
    "H4": StageSpec(
        "H4",
        "build/hardcore/h4-capability-isolation.json",
        "lukart.hardcore.h4-capability-isolation-evidence.v1",
        policy_key="h4_capability_isolation",
        require_internal_digest=True,
    ),
    "H5": StageSpec(
        "H5",
        "build/hardcore/h5-replay-migration.json",
        "lukart.hardcore.h5-replay-migration-evidence.v1",
        policy_key="h5_replay_migration",
        require_internal_digest=True,
    ),
    "H6": StageSpec(
        "H6",
        "build/hardcore/h6-authorization-isolation.json",
        "lukart.hardcore.h6-authorization-evidence.v1",
        policy_key="h6_authorization_isolation",
        require_internal_digest=True,
    ),
    "H7": StageSpec(
        "H7",
        "build/hardcore/h7-recovery-rollback.json",
        "lukart.hardcore.h7-recovery-rollback-evidence.v1",
        policy_key="h7_recovery_rollback",
        require_internal_digest=True,
    ),
    "H8": StageSpec(
        "H8",
        "build/hardcore/h8-scale-concurrency.json",
        "lukart.hardcore.h8-scale-concurrency-evidence.v1",
        policy_key="h8_scale_concurrency",
        require_internal_digest=True,
    ),
    "H9": StageSpec(
        "H9",
        "build/hardcore/h9-tamper-evident-audit.json",
        "lukart.hardcore.h9-audit-evidence.v1",
        policy_key="h9_tamper_evident_audit",
        require_internal_digest=True,
    ),
}


@dataclass(frozen=True, slots=True)
class StageEvidenceDocument:
    stage: str
    path: str
    payload: Mapping[str, object]
    file_sha256: str


@dataclass(frozen=True, slots=True)
class EnterpriseEvidenceDocument:
    path: str
    payload: Mapping[str, object]
    file_sha256: str


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"H10 cannot read evidence artifact: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"H10 evidence artifact must be a JSON object: {path}")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _validate_h10_policy(policy: Mapping[str, object]) -> Mapping[str, object]:
    h10 = _mapping(policy.get("h10_evidence_closure"), label="h10_evidence_closure")
    required: dict[str, object] = {
        "schema": "lukart.hardcore.h10-evidence-closure.v1",
        "manifest_schema": "lukart.hardcore.h10-evidence-manifest.v1",
        "expected_stages": list(STAGE_SPECS),
        "exact_candidate_sha_required": True,
        "canonical_config_digest_required": True,
        "missing_stage": "FAIL",
        "mixed_sha": "FAIL",
        "evidence_digest_mismatch": "FAIL",
        "unknown_schema": "FAIL",
        "failed_stage": "FAIL",
        "engineering_pass_may_be_automated": True,
        "independent_review_state": "INDEPENDENT_REVIEW_REQUIRED",
        "independent_certification_claimed": False,
        "release_mutation_requested": False,
    }
    for key, expected in required.items():
        if h10.get(key) != expected:
            raise RuntimeError(
                f"H10 policy mismatch for {key}: {h10.get(key)!r} != {expected!r}"
            )
    return h10


def _verify_internal_digest(payload: Mapping[str, object], *, stage: str) -> str:
    stored = payload.get("evidence_digest")
    if not isinstance(stored, str):
        raise RuntimeError(f"H10 {stage} internal evidence digest is missing")
    stored = require_hex_digest(stored, field_name=f"{stage.lower()}_evidence_digest")
    unsigned = dict(payload)
    unsigned.pop("evidence_digest", None)
    if content_digest(unsigned) != stored:
        raise RuntimeError(f"H10 {stage} evidence digest mismatch")
    return stored


def _validate_stage_document(
    document: StageEvidenceDocument,
    *,
    candidate_sha: str,
    policy: Mapping[str, object],
) -> dict[str, object]:
    spec = STAGE_SPECS.get(document.stage)
    if spec is None:
        raise RuntimeError(f"H10 unexpected stage: {document.stage}")
    if document.path != spec.path:
        raise RuntimeError(
            f"H10 {document.stage} path mismatch: {document.path!r} != {spec.path!r}"
        )
    file_sha = require_hex_digest(
        document.file_sha256,
        field_name=f"{document.stage.lower()}_file_sha256",
    )
    schema = document.payload.get("schema")
    if schema != spec.schema:
        raise RuntimeError(
            f"H10 unknown/incompatible {document.stage} schema: {schema!r}"
        )
    observed_candidate = document.payload.get("candidate_sha")
    if observed_candidate != candidate_sha:
        raise RuntimeError(
            f"H10 mixed candidate SHA at {document.stage}: "
            f"{observed_candidate!r} != {candidate_sha!r}"
        )
    checked_out_head = document.payload.get("checked_out_head_sha")
    if checked_out_head is not None and checked_out_head != candidate_sha:
        raise RuntimeError(
            f"H10 checked-out HEAD mismatch at {document.stage}: {checked_out_head!r}"
        )
    if spec.require_control_pass and document.payload.get("state") != "CONTROL_PASS":
        raise RuntimeError(
            f"H10 failed stage {document.stage}: state={document.payload.get('state')!r}"
        )

    if spec.policy_key is not None:
        policy_section = _mapping(
            policy.get(spec.policy_key),
            label=f"policy.{spec.policy_key}",
        )
        expected_policy_digest = content_digest(policy_section)
        if document.payload.get("policy_digest") != expected_policy_digest:
            raise RuntimeError(f"H10 {document.stage} policy/config digest mismatch")

    if document.stage == "H2":
        expected_policy_digest = content_digest(policy)
        if document.payload.get("enterprise_policy_digest") != expected_policy_digest:
            raise RuntimeError("H10 H2 canonical config digest mismatch")

    if spec.require_internal_digest:
        evidence_digest = _verify_internal_digest(document.payload, stage=document.stage)
    else:
        evidence_digest = content_digest(document.payload)

    return {
        "stage": document.stage,
        "path": document.path,
        "schema": spec.schema,
        "candidate_sha": candidate_sha,
        "evidence_digest": evidence_digest,
        "artifact_sha256": file_sha,
        "validated_state": "CONTROL_PASS",
    }


def _validate_enterprise_evidence(
    document: EnterpriseEvidenceDocument,
    *,
    candidate_sha: str,
) -> dict[str, object]:
    if document.path != ENTERPRISE_EVIDENCE_PATH:
        raise RuntimeError("H10 Enterprise evidence path mismatch")
    file_sha = require_hex_digest(document.file_sha256, field_name="enterprise_file_sha256")
    payload = document.payload
    if payload.get("schema") != "lukart.enterprise-engineering-evidence.v1":
        raise RuntimeError("H10 unknown/incompatible Enterprise evidence schema")
    if payload.get("candidate_sha") != candidate_sha:
        raise RuntimeError("H10 mixed candidate SHA in Enterprise evidence")
    if payload.get("state") != "INDEPENDENT_REVIEW_REQUIRED":
        raise RuntimeError(
            "H10 Enterprise engineering evidence must preserve independent-review boundary"
        )
    missing = payload.get("missing_stages")
    failed = payload.get("failed_stages")
    if missing != [] or failed != []:
        raise RuntimeError(
            f"H10 incomplete Enterprise engineering evidence: missing={missing!r} failed={failed!r}"
        )
    bundle_digest = payload.get("evidence_bundle_digest")
    if not isinstance(bundle_digest, str):
        raise RuntimeError("H10 Enterprise evidence bundle digest is missing")
    bundle_digest = require_hex_digest(
        bundle_digest,
        field_name="enterprise_evidence_bundle_digest",
    )
    return {
        "path": document.path,
        "schema": payload["schema"],
        "candidate_sha": candidate_sha,
        "state": payload["state"],
        "evidence_bundle_digest": bundle_digest,
        "artifact_sha256": file_sha,
    }


def validate_evidence_set(
    *,
    candidate_sha: str,
    policy: Mapping[str, object],
    stage_documents: Sequence[StageEvidenceDocument],
    enterprise_document: EnterpriseEvidenceDocument,
) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    h10 = _validate_h10_policy(policy)
    config_digest = content_digest(policy)

    seen: set[str] = set()
    documents_by_stage: dict[str, StageEvidenceDocument] = {}
    for document in stage_documents:
        if document.stage in seen:
            raise RuntimeError(f"H10 duplicate stage evidence: {document.stage}")
        seen.add(document.stage)
        documents_by_stage[document.stage] = document

    expected = set(STAGE_SPECS)
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing:
        raise RuntimeError(f"H10 missing stage evidence: {missing}")
    if unexpected:
        raise RuntimeError(f"H10 unexpected stage evidence: {unexpected}")

    stage_descriptors = [
        _validate_stage_document(
            documents_by_stage[stage],
            candidate_sha=candidate,
            policy=policy,
        )
        for stage in STAGE_SPECS
    ]
    enterprise_descriptor = _validate_enterprise_evidence(
        enterprise_document,
        candidate_sha=candidate,
    )

    h3_manifest = _mapping(
        documents_by_stage["H3"].payload.get("artifact_manifest"),
        label="H3 artifact_manifest",
    )
    for stage in ("H1", "H2"):
        document = documents_by_stage[stage]
        if h3_manifest.get(document.path) != document.file_sha256:
            raise RuntimeError(f"H10 H3 manifest does not bind {stage} artifact bytes")
    if h3_manifest.get(enterprise_document.path) != enterprise_document.file_sha256:
        raise RuntimeError("H10 H3 manifest does not bind Enterprise engineering evidence bytes")

    evidence_set_body: dict[str, object] = {
        "schema": "lukart.hardcore.h10-evidence-set.v1",
        "candidate_sha": candidate,
        "config_digest": config_digest,
        "stages": stage_descriptors,
        "enterprise": enterprise_descriptor,
    }
    evidence_set_digest = content_digest(evidence_set_body)

    manifest: dict[str, object] = {
        "schema": h10["manifest_schema"],
        "candidate_sha": candidate,
        "code_identity": {"git_sha": candidate},
        "config_digest": config_digest,
        "stage_count": len(stage_descriptors),
        "expected_stages": list(STAGE_SPECS),
        "stage_evidence": stage_descriptors,
        "enterprise_evidence": enterprise_descriptor,
        "evidence_set_digest": evidence_set_digest,
        "engineering_state": "ENGINEERING_PASS",
        "review_state": "INDEPENDENT_REVIEW_REQUIRED",
        "independent_certification_claimed": False,
        "release_mutation_requested": False,
    }
    manifest["manifest_digest"] = content_digest(manifest)
    return manifest


def build_h10_manifest(candidate_sha: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if candidate != head:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    policy = _load_json_object(POLICY_PATH)
    stage_documents: list[StageEvidenceDocument] = []
    for stage, spec in STAGE_SPECS.items():
        path = ROOT / spec.path
        if not path.is_file():
            raise RuntimeError(f"H10 missing stage evidence artifact: {spec.path}")
        stage_documents.append(
            StageEvidenceDocument(
                stage=stage,
                path=spec.path,
                payload=_load_json_object(path),
                file_sha256=_sha256(path),
            )
        )

    enterprise_path = ROOT / ENTERPRISE_EVIDENCE_PATH
    if not enterprise_path.is_file():
        raise RuntimeError("H10 missing Enterprise engineering evidence artifact")
    enterprise_document = EnterpriseEvidenceDocument(
        path=ENTERPRISE_EVIDENCE_PATH,
        payload=_load_json_object(enterprise_path),
        file_sha256=_sha256(enterprise_path),
    )
    manifest = validate_evidence_set(
        candidate_sha=candidate,
        policy=policy,
        stage_documents=stage_documents,
        enterprise_document=enterprise_document,
    )
    manifest["checked_out_head_sha"] = head
    unsigned = dict(manifest)
    unsigned.pop("manifest_digest", None)
    manifest["manifest_digest"] = content_digest(unsigned)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Close H1-H10 automated engineering evidence on one exact candidate SHA"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/h10-engineering-evidence-manifest.json",
    )
    args = parser.parse_args()

    manifest = build_h10_manifest(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H10_ENGINEERING_EVIDENCE_CLOSURE=PASS")
    print(f"H10_CANDIDATE_SHA={manifest['candidate_sha']}")
    print(f"H10_ENGINEERING_STATE={manifest['engineering_state']}")
    print(f"H10_REVIEW_STATE={manifest['review_state']}")
    print(f"H10_MANIFEST_DIGEST={manifest['manifest_digest']}")
    print(f"H10_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
