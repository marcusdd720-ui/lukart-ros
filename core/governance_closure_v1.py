"""GOV-01 fail-closed governance closure consistency verification.

GitHub live state remains the source of truth for PR/SHA/CI/release state. This module is a
pure verifier over an externally supplied evidence snapshot; it has no network, persistence,
CCL, release, merge, or certification authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

GOVERNANCE_CLOSURE_SCHEMA_V1 = "lukart.governance-closure.v1"
GOVERNANCE_SNAPSHOT_SCHEMA_V1 = "lukart.governance-live-snapshot.v1"
GOVERNANCE_REPORT_SCHEMA_V1 = "lukart.governance-consistency-report.v1"

REQUIRED_PR_WORKFLOWS_V1 = (
    "Architectural Audit 1.0",
    "CI Foundation",
    "Enterprise CodeQL",
    "Enterprise Hardcore Gate",
    "GitHub App Smoke Test",
    "P2 Semantic Intelligence",
    "P3 Hardcore Hardening",
    "Post-v1 v1.1",
    "Production Validation Program",
    "Stage Gate",
    "Stage Orchestrator",
)


class GovernanceClosureError(ValueError):
    """Fail-closed GOV-01 consistency violation."""


class WorkflowOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


def _require_text(value: str, field: str) -> str:
    if not value or value != value.strip():
        raise GovernanceClosureError(f"{field} must be nonblank and canonical")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise GovernanceClosureError(f"{field} cannot contain control characters")
    return value


def _require_sha(value: str, field: str) -> str:
    if len(value) != 40 or not all(
        "0" <= ch <= "9" or "a" <= ch <= "f" for ch in value
    ):
        raise GovernanceClosureError(f"{field} must be a lowercase 40-character Git SHA")
    return value


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkflowEvidenceV1:
    name: str
    outcome: WorkflowOutcome

    def __post_init__(self) -> None:
        _require_text(self.name, "workflow.name")

    def canonical_dict(self) -> dict[str, str]:
        return {"name": self.name, "outcome": self.outcome.value}


@dataclass(frozen=True, slots=True)
class GovernanceLiveSnapshotV1:
    """Externally observed live evidence; never synthesized from governance text."""

    stage_id: str
    implementation_pr: int
    validated_head_sha: str
    merge_sha: str
    merge_parent_shas: tuple[str, ...]
    pr_workflows: tuple[WorkflowEvidenceV1, ...]
    post_merge_success_count: int
    post_merge_non_success_count: int
    baseline_tag_object_sha: str
    baseline_target_commit_sha: str
    schema: str = GOVERNANCE_SNAPSHOT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != GOVERNANCE_SNAPSHOT_SCHEMA_V1:
            raise GovernanceClosureError(f"unsupported snapshot schema: {self.schema}")
        _require_text(self.stage_id, "stage_id")
        if self.implementation_pr < 1:
            raise GovernanceClosureError("implementation_pr must be positive")
        _require_sha(self.validated_head_sha, "validated_head_sha")
        _require_sha(self.merge_sha, "merge_sha")
        if len(self.merge_parent_shas) < 2:
            raise GovernanceClosureError("merge snapshot must expose at least two parents")
        for parent in self.merge_parent_shas:
            _require_sha(parent, "merge_parent_sha")
        if len(set(self.merge_parent_shas)) != len(self.merge_parent_shas):
            raise GovernanceClosureError("merge_parent_shas must be unique")
        if self.validated_head_sha not in self.merge_parent_shas:
            raise GovernanceClosureError("validated head must be a direct merge parent")
        if self.post_merge_success_count < 1:
            raise GovernanceClosureError("post_merge_success_count must be positive")
        if self.post_merge_non_success_count < 0:
            raise GovernanceClosureError("post_merge_non_success_count cannot be negative")
        _require_sha(self.baseline_tag_object_sha, "baseline_tag_object_sha")
        _require_sha(self.baseline_target_commit_sha, "baseline_target_commit_sha")
        names = tuple(item.name for item in self.pr_workflows)
        if len(set(names)) != len(names):
            raise GovernanceClosureError("PR workflow evidence contains duplicate names")
        if tuple(sorted(names)) != tuple(sorted(REQUIRED_PR_WORKFLOWS_V1)):
            raise GovernanceClosureError("PR workflow set does not match fixed GOV-01 v1 set")
        if any(item.outcome is not WorkflowOutcome.SUCCESS for item in self.pr_workflows):
            raise GovernanceClosureError("all required PR workflows must be SUCCESS")
        if self.post_merge_non_success_count != 0:
            raise GovernanceClosureError("post-merge snapshot contains non-success runs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "stage_id": self.stage_id,
            "implementation_pr": self.implementation_pr,
            "validated_head_sha": self.validated_head_sha,
            "merge_sha": self.merge_sha,
            "merge_parent_shas": list(self.merge_parent_shas),
            "pr_workflows": [item.canonical_dict() for item in self.pr_workflows],
            "post_merge_success_count": self.post_merge_success_count,
            "post_merge_non_success_count": self.post_merge_non_success_count,
            "baseline_tag_object_sha": self.baseline_tag_object_sha,
            "baseline_target_commit_sha": self.baseline_target_commit_sha,
        }

    @property
    def identity(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class GovernanceClosureRecordV1:
    """Canonical governance declaration compared with independently observed live state."""

    stage_id: str
    implementation_pr: int
    validated_head_sha: str
    merge_sha: str
    baseline_tag_object_sha: str
    baseline_target_commit_sha: str
    next_stage_id: str
    schema: str = GOVERNANCE_CLOSURE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != GOVERNANCE_CLOSURE_SCHEMA_V1:
            raise GovernanceClosureError(f"unsupported closure record schema: {self.schema}")
        _require_text(self.stage_id, "stage_id")
        _require_text(self.next_stage_id, "next_stage_id")
        if self.stage_id == self.next_stage_id:
            raise GovernanceClosureError("next_stage_id must differ from closed stage_id")
        if self.implementation_pr < 1:
            raise GovernanceClosureError("implementation_pr must be positive")
        _require_sha(self.validated_head_sha, "validated_head_sha")
        _require_sha(self.merge_sha, "merge_sha")
        _require_sha(self.baseline_tag_object_sha, "baseline_tag_object_sha")
        _require_sha(self.baseline_target_commit_sha, "baseline_target_commit_sha")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "stage_id": self.stage_id,
            "implementation_pr": self.implementation_pr,
            "validated_head_sha": self.validated_head_sha,
            "merge_sha": self.merge_sha,
            "baseline_tag_object_sha": self.baseline_tag_object_sha,
            "baseline_target_commit_sha": self.baseline_target_commit_sha,
            "next_stage_id": self.next_stage_id,
        }

    @property
    def identity(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class GovernanceConsistencyReportV1:
    stage_id: str
    closure_record_identity: str
    live_snapshot_identity: str
    next_stage_id: str
    report_identity: str
    schema: str = GOVERNANCE_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != GOVERNANCE_REPORT_SCHEMA_V1:
            raise GovernanceClosureError(f"unsupported report schema: {self.schema}")
        _require_text(self.stage_id, "stage_id")
        _require_text(self.next_stage_id, "next_stage_id")
        for field, value in (
            ("closure_record_identity", self.closure_record_identity),
            ("live_snapshot_identity", self.live_snapshot_identity),
            ("report_identity", self.report_identity),
        ):
            if len(value) != 64 or not all(
                "0" <= ch <= "9" or "a" <= ch <= "f" for ch in value
            ):
                raise GovernanceClosureError(f"{field} must be lowercase sha256 hex")
        if self.report_identity != _digest(self.canonical_body()):
            raise GovernanceClosureError("governance consistency report identity mismatch")

    def canonical_body(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "stage_id": self.stage_id,
            "closure_record_identity": self.closure_record_identity,
            "live_snapshot_identity": self.live_snapshot_identity,
            "next_stage_id": self.next_stage_id,
            "result": "CONSISTENT",
            "authority": "governance-verification-only",
        }


def verify_governance_closure_v1(
    *,
    closure: GovernanceClosureRecordV1,
    live: GovernanceLiveSnapshotV1,
) -> GovernanceConsistencyReportV1:
    """Verify one stage closure against externally observed live GitHub evidence."""

    mismatches: list[str] = []
    if closure.stage_id != live.stage_id:
        mismatches.append("stage_id")
    if closure.implementation_pr != live.implementation_pr:
        mismatches.append("implementation_pr")
    if closure.validated_head_sha != live.validated_head_sha:
        mismatches.append("validated_head_sha")
    if closure.merge_sha != live.merge_sha:
        mismatches.append("merge_sha")
    if closure.baseline_tag_object_sha != live.baseline_tag_object_sha:
        mismatches.append("baseline_tag_object_sha")
    if closure.baseline_target_commit_sha != live.baseline_target_commit_sha:
        mismatches.append("baseline_target_commit_sha")
    if mismatches:
        raise GovernanceClosureError(
            "governance closure does not match live evidence: " + ", ".join(mismatches)
        )

    body = {
        "schema": GOVERNANCE_REPORT_SCHEMA_V1,
        "stage_id": closure.stage_id,
        "closure_record_identity": closure.identity,
        "live_snapshot_identity": live.identity,
        "next_stage_id": closure.next_stage_id,
        "result": "CONSISTENT",
        "authority": "governance-verification-only",
    }
    return GovernanceConsistencyReportV1(
        stage_id=closure.stage_id,
        closure_record_identity=closure.identity,
        live_snapshot_identity=live.identity,
        next_stage_id=closure.next_stage_id,
        report_identity=_digest(body),
    )
