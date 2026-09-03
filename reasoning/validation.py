"""Deterministic validation for evidence-backed reasoning graphs."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.epistemic import KnowledgeStatus
from reasoning.models import ReasoningArtifact


@dataclass(frozen=True, slots=True)
class ReasoningValidationIssue:
    code: str
    message: str
    artifact_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReasoningValidationResult:
    ok: bool
    issues: tuple[ReasoningValidationIssue, ...]


_DERIVED_REQUIRING_SUPPORT = frozenset(
    {
        KnowledgeStatus.CONCLUSION,
        KnowledgeStatus.RECOMMENDATION,
    }
)

_BLOCKING_SUPPORT_STATES = frozenset(
    {
        KnowledgeStatus.UNKNOWN,
        KnowledgeStatus.UNRESOLVED,
        KnowledgeStatus.REJECTED,
    }
)


def _has_evidence_lineage(
    artifact_id: str,
    by_id: dict[str, ReasoningArtifact],
    visiting: set[str] | None = None,
) -> bool:
    artifact = by_id[artifact_id]
    if artifact.evidence_refs:
        return True
    if not artifact.support_ids:
        return False

    active = set() if visiting is None else set(visiting)
    if artifact_id in active:
        return False
    active.add(artifact_id)

    for support_id in artifact.support_ids:
        if support_id in by_id and _has_evidence_lineage(support_id, by_id, active):
            return True
    return False


def _cycle_issues(by_id: dict[str, ReasoningArtifact]) -> list[ReasoningValidationIssue]:
    issues: list[ReasoningValidationIssue] = []
    visited: set[str] = set()
    active: set[str] = set()

    def visit(artifact_id: str) -> None:
        if artifact_id in active:
            issues.append(
                ReasoningValidationIssue(
                    "R003",
                    "support graph contains a cycle",
                    artifact_id,
                )
            )
            return
        if artifact_id in visited:
            return
        visited.add(artifact_id)
        active.add(artifact_id)
        artifact = by_id[artifact_id]
        for support_id in artifact.support_ids:
            if support_id in by_id:
                visit(support_id)
        active.remove(artifact_id)

    for artifact_id in sorted(by_id):
        visit(artifact_id)
    return issues


def validate_reasoning_graph(
    artifacts: tuple[ReasoningArtifact, ...],
) -> ReasoningValidationResult:
    """Validate epistemic support invariants without inferring missing knowledge."""

    issues: list[ReasoningValidationIssue] = []
    by_id: dict[str, ReasoningArtifact] = {}

    for artifact in artifacts:
        if artifact.artifact_id in by_id:
            issues.append(
                ReasoningValidationIssue(
                    "R000",
                    "duplicate artifact_id",
                    artifact.artifact_id,
                )
            )
            continue
        by_id[artifact.artifact_id] = artifact

    for artifact_id in sorted(by_id):
        artifact = by_id[artifact_id]

        if artifact.status is KnowledgeStatus.FACT and not artifact.evidence_refs:
            issues.append(
                ReasoningValidationIssue(
                    "R004",
                    "FACT requires explicit evidence_refs",
                    artifact_id,
                )
            )

        if artifact.status in _DERIVED_REQUIRING_SUPPORT and not artifact.support_ids:
            issues.append(
                ReasoningValidationIssue(
                    "R001",
                    f"{artifact.status.value} requires at least one support artifact",
                    artifact_id,
                )
            )

        for support_id in artifact.support_ids:
            if support_id not in by_id:
                issues.append(
                    ReasoningValidationIssue(
                        "R002",
                        f"missing support artifact: {support_id}",
                        artifact_id,
                    )
                )

        existing_supports = [
            by_id[support_id]
            for support_id in artifact.support_ids
            if support_id in by_id
        ]
        if artifact.status in _DERIVED_REQUIRING_SUPPORT and existing_supports:
            if all(item.status in _BLOCKING_SUPPORT_STATES for item in existing_supports):
                issues.append(
                    ReasoningValidationIssue(
                        "R006",
                        "derived result is supported only by unresolved/rejected knowledge",
                        artifact_id,
                    )
                )
            if not _has_evidence_lineage(artifact_id, by_id):
                issues.append(
                    ReasoningValidationIssue(
                        "R005",
                        "derived result has no evidence-backed support lineage",
                        artifact_id,
                    )
                )

    issues.extend(_cycle_issues(by_id))
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (item.artifact_id or "", item.code, item.message),
        )
    )
    return ReasoningValidationResult(ok=not ordered, issues=ordered)
