from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.hardcore_h1_validate import BASELINE_DOCUMENTS, validate_snapshot

CANDIDATE = "a" * 40
RELEASE = "b" * 40


def _policy() -> dict[str, object]:
    return {
        "baseline": {
            "v1_0_1_sha": RELEASE,
            "v1_0_1_immutable": True,
        }
    }


def _documents() -> dict[str, str]:
    return {
        path: f"Canonical baseline: `v1.0.1 @ {RELEASE}`\n" for path in BASELINE_DOCUMENTS
    }


def _workflow() -> str:
    return (
        "on:\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  enterprise-gate:\n"
        "    steps:\n"
        "      - uses: actions/checkout@" + "c" * 40 + "\n"
        "        with:\n"
        "          fetch-depth: 0\n"
    )


def test_h1_integrity_accepts_exact_candidate_and_historical_tag() -> None:
    evidence = validate_snapshot(
        candidate_sha=CANDIDATE,
        head_sha=CANDIDATE,
        tag_sha=RELEASE,
        policy=_policy(),
        documents=_documents(),
        workflow_text=_workflow(),
    )
    assert evidence["state"] == "CONTROL_PASS"
    assert evidence["candidate_sha"] == CANDIDATE
    assert evidence["historical_release_sha"] == RELEASE
    assert set(evidence["canonical_document_digests"]) == set(BASELINE_DOCUMENTS)


def test_h1_integrity_rejects_candidate_head_mismatch() -> None:
    with pytest.raises(RuntimeError, match="exact-SHA mismatch"):
        validate_snapshot(
            candidate_sha=CANDIDATE,
            head_sha="d" * 40,
            tag_sha=RELEASE,
            policy=_policy(),
            documents=_documents(),
            workflow_text=_workflow(),
        )


def test_h1_integrity_rejects_policy_release_identity_drift() -> None:
    policy = deepcopy(_policy())
    baseline = policy["baseline"]
    assert isinstance(baseline, dict)
    baseline["v1_0_1_sha"] = "e" * 40
    with pytest.raises(RuntimeError, match="historical release identity mismatch"):
        validate_snapshot(
            candidate_sha=CANDIDATE,
            head_sha=CANDIDATE,
            tag_sha=RELEASE,
            policy=policy,
            documents=_documents(),
            workflow_text=_workflow(),
        )


def test_h1_integrity_rejects_canonical_document_baseline_drift() -> None:
    documents = _documents()
    documents["MASTER_PLAN.md"] = f"Canonical baseline: `v1.0.1 @ {'f' * 40}`\n"
    with pytest.raises(RuntimeError, match="canonical baseline drift"):
        validate_snapshot(
            candidate_sha=CANDIDATE,
            head_sha=CANDIDATE,
            tag_sha=RELEASE,
            policy=_policy(),
            documents=documents,
            workflow_text=_workflow(),
        )


def test_h1_integrity_rejects_missing_post_merge_main_gate() -> None:
    workflow = _workflow().replace("  push:\n    branches: [main]\n", "")
    with pytest.raises(RuntimeError, match="lacks post-merge push validation"):
        validate_snapshot(
            candidate_sha=CANDIDATE,
            head_sha=CANDIDATE,
            tag_sha=RELEASE,
            policy=_policy(),
            documents=_documents(),
            workflow_text=workflow,
        )


def test_h1_integrity_rejects_checkout_that_cannot_resolve_historical_tag() -> None:
    workflow = _workflow().replace("fetch-depth: 0", "fetch-depth: 1")
    with pytest.raises(RuntimeError, match="full tag/history fetch"):
        validate_snapshot(
            candidate_sha=CANDIDATE,
            head_sha=CANDIDATE,
            tag_sha=RELEASE,
            policy=_policy(),
            documents=_documents(),
            workflow_text=workflow,
        )
