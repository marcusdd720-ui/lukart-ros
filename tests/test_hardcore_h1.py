from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.hardcore_h1_validate import BASELINE_DOCUMENTS, validate_snapshot

CANDIDATE = "a" * 40
RELEASE_COMMIT = "b" * 40
TAG_OBJECT = "c" * 40


def _policy() -> dict[str, object]:
    return {
        "baseline": {
            "v1_0_1_sha": RELEASE_COMMIT,
            "v1_0_1_tag_object_sha": TAG_OBJECT,
            "v1_0_1_immutable": True,
        }
    }


def _documents() -> dict[str, str]:
    return {
        path: (
            f"Canonical baseline: `v1.0.1 @ {RELEASE_COMMIT}`\n"
            f"Historical tag identity: `v1.0.1 tag object @ {TAG_OBJECT}`\n"
        )
        for path in BASELINE_DOCUMENTS
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
        "      - uses: actions/checkout@" + "d" * 40 + "\n"
        "        with:\n"
        "          fetch-depth: 0\n"
    )


def _validate(
    *,
    candidate_sha: str = CANDIDATE,
    head_sha: str = CANDIDATE,
    tag_object_sha: str = TAG_OBJECT,
    release_commit_sha: str = RELEASE_COMMIT,
    policy: dict[str, object] | None = None,
    documents: dict[str, str] | None = None,
    workflow_text: str | None = None,
) -> dict[str, object]:
    return validate_snapshot(
        candidate_sha=candidate_sha,
        head_sha=head_sha,
        tag_object_sha=tag_object_sha,
        release_commit_sha=release_commit_sha,
        policy=_policy() if policy is None else policy,
        documents=_documents() if documents is None else documents,
        workflow_text=_workflow() if workflow_text is None else workflow_text,
    )


def test_h1_integrity_accepts_exact_candidate_and_annotated_historical_tag() -> None:
    evidence = _validate()
    assert evidence["schema"] == "lukart.hardcore-h1-evidence.v2"
    assert evidence["state"] == "CONTROL_PASS"
    assert evidence["candidate_sha"] == CANDIDATE
    assert evidence["historical_release_commit_sha"] == RELEASE_COMMIT
    assert evidence["historical_release_tag_object_sha"] == TAG_OBJECT
    document_digests = evidence["canonical_document_digests"]
    assert isinstance(document_digests, dict)
    assert set(document_digests) == set(BASELINE_DOCUMENTS)


def test_h1_integrity_rejects_candidate_head_mismatch() -> None:
    with pytest.raises(RuntimeError, match="exact-SHA mismatch"):
        _validate(head_sha="e" * 40)


def test_h1_integrity_rejects_policy_release_commit_identity_drift() -> None:
    policy = deepcopy(_policy())
    baseline = policy["baseline"]
    assert isinstance(baseline, dict)
    baseline["v1_0_1_sha"] = "f" * 40
    with pytest.raises(RuntimeError, match="release commit identity mismatch"):
        _validate(policy=policy)


def test_h1_integrity_rejects_policy_tag_object_identity_drift() -> None:
    policy = deepcopy(_policy())
    baseline = policy["baseline"]
    assert isinstance(baseline, dict)
    baseline["v1_0_1_tag_object_sha"] = "1" * 40
    with pytest.raises(RuntimeError, match="annotated tag identity mismatch"):
        _validate(policy=policy)


def test_h1_integrity_rejects_canonical_release_commit_drift() -> None:
    documents = _documents()
    documents["MASTER_PLAN.md"] = documents["MASTER_PLAN.md"].replace(
        RELEASE_COMMIT,
        "2" * 40,
    )
    with pytest.raises(RuntimeError, match="canonical release commit drift"):
        _validate(documents=documents)


def test_h1_integrity_rejects_canonical_tag_object_drift() -> None:
    documents = _documents()
    documents["MASTER_PLAN.md"] = documents["MASTER_PLAN.md"].replace(
        TAG_OBJECT,
        "3" * 40,
    )
    with pytest.raises(RuntimeError, match="canonical annotated tag drift"):
        _validate(documents=documents)


def test_h1_integrity_rejects_missing_post_merge_main_gate() -> None:
    workflow = _workflow().replace("  push:\n    branches: [main]\n", "")
    with pytest.raises(RuntimeError, match="lacks post-merge push validation"):
        _validate(workflow_text=workflow)


def test_h1_integrity_rejects_checkout_that_cannot_resolve_historical_tag() -> None:
    workflow = _workflow().replace("fetch-depth: 0", "fetch-depth: 1")
    with pytest.raises(RuntimeError, match="full tag/history fetch"):
        _validate(workflow_text=workflow)
