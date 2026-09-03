import pytest

from knowledge.epistemic import (
    EpistemicStatusMachine,
    EpistemicTransitionError,
    EpistemicTransitionRequest,
    KnowledgeStatus,
)


def test_claim_to_fact_requires_new_evidence() -> None:
    machine = EpistemicStatusMachine()

    decision = machine.decide(
        EpistemicTransitionRequest(
            source=KnowledgeStatus.CLAIM,
            target=KnowledgeStatus.FACT,
        )
    )

    assert decision.allowed is False
    assert decision.reason == "promotion to FACT requires new evidence"


def test_claim_to_fact_with_evidence_is_allowed() -> None:
    machine = EpistemicStatusMachine()

    decision = machine.require(
        EpistemicTransitionRequest(
            source=KnowledgeStatus.CLAIM,
            target=KnowledgeStatus.FACT,
            evidence_refs=("evidence:doc-1#p1:10-20",),
        )
    )

    assert decision.allowed is True
    assert decision.target is KnowledgeStatus.FACT


def test_fact_cannot_be_silently_relabelled_as_recommendation() -> None:
    machine = EpistemicStatusMachine()

    with pytest.raises(EpistemicTransitionError, match="silently relabeled"):
        machine.require(
            EpistemicTransitionRequest(
                source=KnowledgeStatus.FACT,
                target=KnowledgeStatus.RECOMMENDATION,
            )
        )


def test_rejection_requires_rationale() -> None:
    machine = EpistemicStatusMachine()

    denied = machine.decide(
        EpistemicTransitionRequest(
            source=KnowledgeStatus.HYPOTHESIS,
            target=KnowledgeStatus.REJECTED,
        )
    )
    allowed = machine.decide(
        EpistemicTransitionRequest(
            source=KnowledgeStatus.HYPOTHESIS,
            target=KnowledgeStatus.REJECTED,
            rationale="contradicted by source evidence",
        )
    )

    assert denied.allowed is False
    assert allowed.allowed is True
