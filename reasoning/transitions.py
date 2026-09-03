"""Epistemic transitions for reasoning artifacts."""

from __future__ import annotations

from dataclasses import replace

from knowledge.epistemic import (
    EpistemicStatusMachine,
    EpistemicTransitionRequest,
    KnowledgeStatus,
)
from reasoning.models import ReasoningArtifact


def transition_artifact(
    artifact: ReasoningArtifact,
    target: KnowledgeStatus,
    *,
    new_evidence_refs: tuple[str, ...] = (),
    rationale: str = "",
    machine: EpistemicStatusMachine | None = None,
) -> ReasoningArtifact:
    """Return a new artifact only when the canonical epistemic policy authorizes it."""

    policy = machine or EpistemicStatusMachine()
    policy.require(
        EpistemicTransitionRequest(
            source=artifact.status,
            target=target,
            evidence_refs=new_evidence_refs,
            rationale=rationale,
        )
    )
    merged_evidence = tuple(dict.fromkeys((*artifact.evidence_refs, *new_evidence_refs)))
    return replace(
        artifact,
        status=target,
        evidence_refs=merged_evidence,
        rationale=rationale.strip() or artifact.rationale,
    )
