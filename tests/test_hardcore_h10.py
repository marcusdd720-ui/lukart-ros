from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping

import pytest

from core.p3.contracts import content_digest
from scripts.hardcore_h10_closure import (
    ENTERPRISE_EVIDENCE_PATH,
    STAGE_SPECS,
    EnterpriseEvidenceDocument,
    StageEvidenceDocument,
    validate_evidence_set,
)

CANDIDATE = "a" * 40


def _file_digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _policy() -> dict[str, object]:
    policy: dict[str, object] = {
        "schema": "lukart.enterprise-policy.v1",
        "h4_capability_isolation": {"schema": "h4"},
        "h5_replay_migration": {"schema": "h5"},
        "h6_authorization_isolation": {"schema": "h6"},
        "h7_recovery_rollback": {"schema": "h7"},
        "h8_scale_concurrency": {"schema": "h8"},
        "h9_tamper_evident_audit": {"schema": "h9"},
        "h10_evidence_closure": {
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
        },
    }
    return policy


def _self_digest(payload: dict[str, object]) -> dict[str, object]:
    document = dict(payload)
    document["evidence_digest"] = content_digest(document)
    return document


def _documents(
    policy: Mapping[str, object],
) -> tuple[list[StageEvidenceDocument], EnterpriseEvidenceDocument]:
    file_digests = {stage: _file_digest(stage) for stage in STAGE_SPECS}
    enterprise_digest = _file_digest("enterprise")
    documents: list[StageEvidenceDocument] = []

    for stage, spec in STAGE_SPECS.items():
        payload: dict[str, object] = {
            "schema": spec.schema,
            "candidate_sha": CANDIDATE,
        }
        if stage != "H3":
            payload["checked_out_head_sha"] = CANDIDATE
        if spec.require_control_pass:
            payload["state"] = "CONTROL_PASS"
        if spec.policy_key is not None:
            section = policy[spec.policy_key]
            payload["policy_digest"] = content_digest(section)
        if stage == "H2":
            payload["enterprise_policy_digest"] = content_digest(policy)
        if stage == "H3":
            payload["artifact_manifest"] = {
                STAGE_SPECS["H1"].path: file_digests["H1"],
                STAGE_SPECS["H2"].path: file_digests["H2"],
                ENTERPRISE_EVIDENCE_PATH: enterprise_digest,
            }
            payload["provenance_digest"] = _file_digest("h3-provenance")
        if spec.require_internal_digest:
            payload = _self_digest(payload)
        documents.append(
            StageEvidenceDocument(
                stage=stage,
                path=spec.path,
                payload=payload,
                file_sha256=file_digests[stage],
            )
        )

    enterprise = EnterpriseEvidenceDocument(
        path=ENTERPRISE_EVIDENCE_PATH,
        payload={
            "schema": "lukart.enterprise-engineering-evidence.v1",
            "candidate_sha": CANDIDATE,
            "state": "INDEPENDENT_REVIEW_REQUIRED",
            "evidence_bundle_digest": _file_digest("enterprise-bundle"),
            "missing_stages": [],
            "failed_stages": [],
            "independent_review_digest": None,
        },
        file_sha256=enterprise_digest,
    )
    return documents, enterprise


def _replace_document(
    documents: list[StageEvidenceDocument],
    stage: str,
    payload: Mapping[str, object],
) -> list[StageEvidenceDocument]:
    result: list[StageEvidenceDocument] = []
    for document in documents:
        if document.stage == stage:
            result.append(
                StageEvidenceDocument(
                    stage=document.stage,
                    path=document.path,
                    payload=payload,
                    file_sha256=document.file_sha256,
                )
            )
        else:
            result.append(document)
    return result


def test_h10_valid_single_sha_set_closes_engineering_only() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)

    manifest = validate_evidence_set(
        candidate_sha=CANDIDATE,
        policy=policy,
        stage_documents=documents,
        enterprise_document=enterprise,
    )

    assert manifest["stage_count"] == 9
    assert manifest["engineering_state"] == "ENGINEERING_PASS"
    assert manifest["review_state"] == "INDEPENDENT_REVIEW_REQUIRED"
    assert manifest["independent_certification_claimed"] is False
    assert manifest["release_mutation_requested"] is False
    assert isinstance(manifest["manifest_digest"], str)


def test_h10_mixed_candidate_sha_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H7")
    payload = dict(target.payload)
    payload["candidate_sha"] = "b" * 40
    payload["evidence_digest"] = content_digest(
        {key: value for key, value in payload.items() if key != "evidence_digest"}
    )

    with pytest.raises(RuntimeError, match="mixed candidate SHA"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H7", payload),
            enterprise_document=enterprise,
        )


def test_h10_missing_stage_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)

    with pytest.raises(RuntimeError, match="missing stage evidence"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=[item for item in documents if item.stage != "H6"],
            enterprise_document=enterprise,
        )


def test_h10_duplicate_stage_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)

    with pytest.raises(RuntimeError, match="duplicate stage evidence"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=[*documents, documents[0]],
            enterprise_document=enterprise,
        )


def test_h10_unknown_schema_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H8")
    payload = dict(target.payload)
    payload["schema"] = "lukart.hardcore.h8-scale-concurrency-evidence.v999"

    with pytest.raises(RuntimeError, match="unknown/incompatible H8 schema"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H8", payload),
            enterprise_document=enterprise,
        )


def test_h10_internal_evidence_digest_tamper_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H5")
    payload = dict(target.payload)
    payload["extra"] = "tampered-after-self-digest"

    with pytest.raises(RuntimeError, match="H5 evidence digest mismatch"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H5", payload),
            enterprise_document=enterprise,
        )


def test_h10_failed_control_state_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H6")
    payload = dict(target.payload)
    payload["state"] = "FAIL"
    payload["evidence_digest"] = content_digest(
        {key: value for key, value in payload.items() if key != "evidence_digest"}
    )

    with pytest.raises(RuntimeError, match="failed stage H6"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H6", payload),
            enterprise_document=enterprise,
        )


def test_h10_checked_out_head_mismatch_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H4")
    payload = dict(target.payload)
    payload["checked_out_head_sha"] = "b" * 40
    payload["evidence_digest"] = content_digest(
        {key: value for key, value in payload.items() if key != "evidence_digest"}
    )

    with pytest.raises(RuntimeError, match="checked-out HEAD mismatch"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H4", payload),
            enterprise_document=enterprise,
        )


def test_h10_config_digest_drift_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    mutated = copy.deepcopy(policy)
    h8 = mutated["h8_scale_concurrency"]
    assert isinstance(h8, dict)
    h8["new_semantic_control"] = True

    with pytest.raises(RuntimeError, match="config digest mismatch|policy/config digest mismatch"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=mutated,
            stage_documents=documents,
            enterprise_document=enterprise,
        )


def test_h10_h3_manifest_binding_gap_fails_closed() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    target = next(item for item in documents if item.stage == "H3")
    payload = dict(target.payload)
    raw_manifest = payload["artifact_manifest"]
    assert isinstance(raw_manifest, dict)
    artifact_manifest = dict(raw_manifest)
    artifact_manifest[STAGE_SPECS["H1"].path] = "f" * 64
    payload["artifact_manifest"] = artifact_manifest
    payload["evidence_digest"] = content_digest(
        {key: value for key, value in payload.items() if key != "evidence_digest"}
    )

    with pytest.raises(RuntimeError, match="H3 manifest does not bind H1"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=_replace_document(documents, "H3", payload),
            enterprise_document=enterprise,
        )


def test_h10_enterprise_boundary_cannot_be_promoted_by_automation() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    promoted = EnterpriseEvidenceDocument(
        path=enterprise.path,
        payload={**enterprise.payload, "state": "CERTIFIED"},
        file_sha256=enterprise.file_sha256,
    )

    with pytest.raises(RuntimeError, match="independent-review boundary"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=documents,
            enterprise_document=promoted,
        )


def test_h10_policy_cannot_claim_independent_certification_or_release_mutation() -> None:
    policy = _policy()
    documents, enterprise = _documents(policy)
    h10 = policy["h10_evidence_closure"]
    assert isinstance(h10, dict)
    h10["independent_certification_claimed"] = True
    h10["release_mutation_requested"] = True

    with pytest.raises(RuntimeError, match="H10 policy mismatch"):
        validate_evidence_set(
            candidate_sha=CANDIDATE,
            policy=policy,
            stage_documents=documents,
            enterprise_document=enterprise,
        )
