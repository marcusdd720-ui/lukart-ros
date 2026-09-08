from __future__ import annotations

from dataclasses import replace

import pytest

from core.governance_closure_v1 import (
    GOVERNANCE_CLOSURE_SCHEMA_V1,
    REQUIRED_PR_WORKFLOWS_V1,
    GovernanceClosureError,
    GovernanceClosureRecordV1,
    GovernanceLiveSnapshotV1,
    WorkflowEvidenceV1,
    WorkflowOutcome,
    verify_governance_closure_v1,
)

HEAD = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40
TAG = "d" * 40
TARGET = "e" * 40


def _workflows() -> tuple[WorkflowEvidenceV1, ...]:
    return tuple(
        WorkflowEvidenceV1(name=name, outcome=WorkflowOutcome.SUCCESS)
        for name in REQUIRED_PR_WORKFLOWS_V1
    )


def _live() -> GovernanceLiveSnapshotV1:
    return GovernanceLiveSnapshotV1(
        stage_id="PVE-01",
        implementation_pr=164,
        validated_head_sha=HEAD,
        merge_sha=MERGE,
        merge_parent_shas=(BASE, HEAD),
        pr_workflows=_workflows(),
        post_merge_success_count=9,
        post_merge_non_success_count=0,
        baseline_tag_object_sha=TAG,
        baseline_target_commit_sha=TARGET,
    )


def _closure() -> GovernanceClosureRecordV1:
    return GovernanceClosureRecordV1(
        stage_id="PVE-01",
        implementation_pr=164,
        validated_head_sha=HEAD,
        merge_sha=MERGE,
        baseline_tag_object_sha=TAG,
        baseline_target_commit_sha=TARGET,
        next_stage_id="GOV-01",
    )


def test_consistent_closure_is_content_addressed_and_deterministic() -> None:
    first = verify_governance_closure_v1(closure=_closure(), live=_live())
    second = verify_governance_closure_v1(closure=_closure(), live=_live())

    assert first == second
    assert first.report_identity == second.report_identity
    assert first.stage_id == "PVE-01"
    assert first.next_stage_id == "GOV-01"


def test_fixed_workflow_registry_cannot_be_reduced() -> None:
    with pytest.raises(GovernanceClosureError, match="fixed GOV-01 v1 set"):
        replace(_live(), pr_workflows=_workflows()[:-1])


def test_duplicate_workflow_fails_closed() -> None:
    duplicate = _workflows() + (_workflows()[0],)
    with pytest.raises(GovernanceClosureError, match="duplicate"):
        replace(_live(), pr_workflows=duplicate)


def test_failed_required_workflow_fails_closed() -> None:
    workflows = list(_workflows())
    workflows[0] = replace(workflows[0], outcome=WorkflowOutcome.FAILURE)
    with pytest.raises(GovernanceClosureError, match="must be SUCCESS"):
        replace(_live(), pr_workflows=tuple(workflows))


def test_non_success_post_merge_state_fails_closed() -> None:
    with pytest.raises(GovernanceClosureError, match="non-success"):
        replace(_live(), post_merge_non_success_count=1)


def test_moved_head_not_present_in_merge_parents_fails_closed() -> None:
    with pytest.raises(GovernanceClosureError, match="direct merge parent"):
        replace(_live(), validated_head_sha="f" * 40)


def test_stale_governance_head_fails_closed() -> None:
    closure = replace(_closure(), validated_head_sha="f" * 40)
    with pytest.raises(GovernanceClosureError, match="validated_head_sha"):
        verify_governance_closure_v1(closure=closure, live=_live())


def test_wrong_merge_identity_fails_closed() -> None:
    closure = replace(_closure(), merge_sha="f" * 40)
    with pytest.raises(GovernanceClosureError, match="merge_sha"):
        verify_governance_closure_v1(closure=closure, live=_live())


def test_cross_stage_substitution_fails_closed() -> None:
    closure = replace(_closure(), stage_id="PRC-01")
    with pytest.raises(GovernanceClosureError, match="stage_id"):
        verify_governance_closure_v1(closure=closure, live=_live())


def test_baseline_tag_drift_fails_closed() -> None:
    closure = replace(_closure(), baseline_tag_object_sha="f" * 40)
    with pytest.raises(GovernanceClosureError, match="baseline_tag_object_sha"):
        verify_governance_closure_v1(closure=closure, live=_live())


def test_baseline_target_drift_fails_closed() -> None:
    closure = replace(_closure(), baseline_target_commit_sha="f" * 40)
    with pytest.raises(GovernanceClosureError, match="baseline_target_commit_sha"):
        verify_governance_closure_v1(closure=closure, live=_live())


def test_malformed_git_sha_fails_closed() -> None:
    with pytest.raises(GovernanceClosureError, match="40-character Git SHA"):
        replace(_closure(), merge_sha="ABC")


def test_unknown_schema_fails_closed() -> None:
    with pytest.raises(GovernanceClosureError, match="unsupported closure record schema"):
        replace(_closure(), schema="lukart.governance-closure.v2")


def test_closed_stage_cannot_reactivate_itself_as_next_stage() -> None:
    with pytest.raises(GovernanceClosureError, match="must differ"):
        replace(_closure(), next_stage_id="PVE-01")


def test_schema_constant_is_stable() -> None:
    assert GOVERNANCE_CLOSURE_SCHEMA_V1 == "lukart.governance-closure.v1"
