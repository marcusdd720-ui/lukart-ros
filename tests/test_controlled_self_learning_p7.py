from __future__ import annotations

from uuid import UUID

import pytest

from core.models.ids import AgentId
from learning.adversarial_verification import (
    AdversarialVerificationGate,
    AdversarialVerificationStatus,
    ChallengeAssessment,
    ChallengeFinding,
    ChallengeResolution,
    ChallengeResolutionStatus,
    EvidenceVerification,
    EvidenceVerificationStatus,
    ReviewAssessment,
    ReviewStatus,
    VerificationProposal,
)
from learning.controlled_self_learning import (
    ControlledSelfLearningGate,
    SelfLearningCycleStatus,
)
from learning.experiment import ExperimentContract, MetricDirection, MetricGuardrail
from learning.models import ChangeKind, LearningCandidate, LearningSource, MeasuredFailure
from learning.promotion import MetricDelta, PromotionDecision, PromotionStatus
from learning.semantic_self_healing import (
    RepairReadinessDecision,
    RepairReadinessStatus,
    RevalidationMode,
)


def _digest(character: str) -> str:
    return character * 64


def _agent(number: int) -> AgentId:
    return AgentId(UUID(int=number))


def _proposal(*, generator: int = 1, subject_digest: str | None = None) -> VerificationProposal:
    return VerificationProposal(
        proposal_id="P7-PROPOSAL-1",
        generator_agent_id=_agent(generator),
        subject_type="measured_failure",
        subject_digest=subject_digest or _digest("a"),
        claim_digests=(_digest("b"),),
        evidence_digests=(_digest("c"), _digest("d")),
    )


def _challenge(
    proposal: VerificationProposal,
    *,
    actor: int = 2,
    code: str = "CH-1",
    blocking: bool = True,
) -> ChallengeAssessment:
    return ChallengeAssessment(
        challenger_agent_id=_agent(actor),
        proposal_digest=proposal.digest(),
        findings=(
            ChallengeFinding(
                code=code,
                claim_digest=proposal.claim_digests[0],
                rationale="challenge the evidentiary support",
                blocking=blocking,
                evidence_digests=(proposal.evidence_digests[0],),
            ),
        ),
    )


def _evidence(
    proposal: VerificationProposal,
    *,
    actor: int = 3,
    status: EvidenceVerificationStatus = EvidenceVerificationStatus.PASS,
    resolution_status: ChallengeResolutionStatus = ChallengeResolutionStatus.RESOLVED,
    challenge_code: str = "CH-1",
    rejected: tuple[str, ...] = (),
    unsupported: tuple[str, ...] = (),
) -> EvidenceVerification:
    return EvidenceVerification(
        verifier_agent_id=_agent(actor),
        proposal_digest=proposal.digest(),
        status=status,
        checked_evidence_digests=proposal.evidence_digests,
        rejected_evidence_digests=rejected,
        unsupported_claim_digests=unsupported,
        challenge_resolutions=(
            ChallengeResolution(
                challenge_code=challenge_code,
                status=resolution_status,
                evidence_digests=(proposal.evidence_digests[0],),
                rationale="resolved against independently checked evidence",
            ),
        ),
    )


def _review(
    proposal: VerificationProposal,
    *,
    actor: int = 4,
    status: ReviewStatus = ReviewStatus.PASS,
) -> ReviewAssessment:
    return ReviewAssessment(
        reviewer_agent_id=_agent(actor),
        proposal_digest=proposal.digest(),
        status=status,
        rationale="independent process review",
    )


def _verified_decision(subject_digest: str) -> tuple[VerificationProposal, object]:
    proposal = _proposal(subject_digest=subject_digest)
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal),
        _review(proposal),
    )
    return proposal, decision


def _failure() -> MeasuredFailure:
    return MeasuredFailure(
        failure_id="FAIL-P7-1",
        source=LearningSource.REASONING_KQM,
        corpus_id="reasoning-gold-v1",
        corpus_version="1.0.0",
        split="development",
        evaluator_version="1.0.0",
        source_sha="1" * 40,
        case_id="CASE-P7-1",
        code="unsupported_conclusion",
        expected="abstain",
        actual="conclude",
        result_digest=_digest("e"),
        report_digest=_digest("f"),
    )


def _candidate(failure: MeasuredFailure) -> LearningCandidate:
    return LearningCandidate(
        candidate_id="LC-P7-1",
        source_failure_digest=failure.digest(),
        target_component="reasoning.engine",
        change_kind=ChangeKind.RULE,
        problem_statement="unsupported conclusion escaped the reasoning gate",
        hypothesis="stricter support rule will force abstention",
        success_criteria=("unsafe_conclusion_rate does not regress",),
    )


def _experiment(candidate: LearningCandidate) -> ExperimentContract:
    return ExperimentContract(
        experiment_id="EXP-P7-1",
        candidate_digest=candidate.digest(),
        target_component=candidate.target_component,
        baseline_revision="1" * 40,
        candidate_revision="2" * 40,
        sandbox_id="sandbox-p7",
        allowed_splits=("development", "validation"),
        guardrails=(
            MetricGuardrail(
                name="unsafe_conclusion_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                max_regression=0.0,
            ),
        ),
        max_runs=2,
    )


def _promotion(
    experiment: ExperimentContract,
    *,
    status: PromotionStatus = PromotionStatus.ELIGIBLE_FOR_PROMOTION,
    improvement: float = 0.2,
) -> PromotionDecision:
    return PromotionDecision(
        status=status,
        reason="measured result",
        contract_digest=experiment.digest(),
        deltas=(
            MetricDelta(
                name="unsafe_conclusion_rate",
                baseline=0.2,
                candidate=0.0 if improvement >= 0 else 0.4,
                signed_improvement=improvement,
                allowed_regression=0.0,
            ),
        ),
    )


def _readiness(candidate: LearningCandidate) -> RepairReadinessDecision:
    return RepairReadinessDecision(
        status=RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION,
        reason="P6 passed",
        candidate_digest=candidate.digest(),
        validation_evidence_digest=_digest("9"),
        revalidation_mode=RevalidationMode.SELECTIVE,
    )


def test_adversarial_verification_passes_only_after_independent_resolution() -> None:
    proposal = _proposal()
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal),
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.VERIFIED
    assert decision.proposal_digest == proposal.digest()


def test_majority_cannot_override_evidence_veto() -> None:
    proposal = _proposal()
    challenges = (
        ChallengeAssessment(_agent(2), proposal.digest(), ()),
        ChallengeAssessment(_agent(5), proposal.digest(), ()),
        ChallengeAssessment(_agent(6), proposal.digest(), ()),
    )
    evidence = EvidenceVerification(
        verifier_agent_id=_agent(3),
        proposal_digest=proposal.digest(),
        status=EvidenceVerificationStatus.FAIL,
        checked_evidence_digests=proposal.evidence_digests,
        rejected_evidence_digests=(proposal.evidence_digests[0],),
        rationale="one source failed provenance verification",
    )

    decision = AdversarialVerificationGate().evaluate(
        proposal,
        challenges,
        evidence,
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.REJECTED
    assert "evidence" in decision.reason


def test_missing_blocking_challenge_resolution_forces_inconclusive() -> None:
    proposal = _proposal()
    evidence = EvidenceVerification(
        verifier_agent_id=_agent(3),
        proposal_digest=proposal.digest(),
        status=EvidenceVerificationStatus.PASS,
        checked_evidence_digests=proposal.evidence_digests,
    )

    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        evidence,
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.INCONCLUSIVE


def test_upheld_blocking_challenge_rejects_proposal() -> None:
    proposal = _proposal()
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal, resolution_status=ChallengeResolutionStatus.UPHELD),
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.REJECTED


def test_same_identity_cannot_generate_and_verify() -> None:
    proposal = _proposal(generator=3)
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal, actor=3),
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.REJECTED
    assert "independent" in decision.reason


def test_unchecked_proposal_evidence_forces_inconclusive() -> None:
    proposal = _proposal()
    evidence = EvidenceVerification(
        verifier_agent_id=_agent(3),
        proposal_digest=proposal.digest(),
        status=EvidenceVerificationStatus.PASS,
        checked_evidence_digests=(proposal.evidence_digests[0],),
        challenge_resolutions=(
            ChallengeResolution(
                challenge_code="CH-1",
                status=ChallengeResolutionStatus.RESOLVED,
                evidence_digests=(proposal.evidence_digests[0],),
                rationale="partial evidence check",
            ),
        ),
    )

    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        evidence,
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.INCONCLUSIVE


def test_unknown_challenge_resolution_is_rejected() -> None:
    proposal = _proposal()
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal, challenge_code="UNKNOWN"),
        _review(proposal),
    )

    assert decision.status is AdversarialVerificationStatus.REJECTED


def test_controlled_self_learning_closes_only_existing_p4_p6_path() -> None:
    failure = _failure()
    _, verification = _verified_decision(failure.digest())
    candidate = _candidate(failure)
    experiment = _experiment(candidate)

    decision = ControlledSelfLearningGate().evaluate(
        failure,
        verification,  # type: ignore[arg-type]
        candidate,
        experiment,
        _promotion(experiment),
        _readiness(candidate),
    )

    assert decision.status is SelfLearningCycleStatus.READY_FOR_EXISTING_RELEASE_PATH
    assert decision.failure_digest == failure.digest()
    assert decision.candidate_digest == candidate.digest()


def test_measured_guardrail_regression_suspends_candidate() -> None:
    failure = _failure()
    _, verification = _verified_decision(failure.digest())
    candidate = _candidate(failure)
    experiment = _experiment(candidate)

    decision = ControlledSelfLearningGate().evaluate(
        failure,
        verification,  # type: ignore[arg-type]
        candidate,
        experiment,
        _promotion(experiment, status=PromotionStatus.REJECTED, improvement=-0.2),
        _readiness(candidate),
    )

    assert decision.status is SelfLearningCycleStatus.SUSPENDED


def test_unverified_learning_trigger_cannot_enter_self_learning_cycle() -> None:
    failure = _failure()
    proposal = _proposal(subject_digest=failure.digest())
    verification = AdversarialVerificationGate().evaluate(
        proposal,
        (_challenge(proposal),),
        _evidence(proposal, status=EvidenceVerificationStatus.INCONCLUSIVE),
        _review(proposal),
    )
    candidate = _candidate(failure)
    experiment = _experiment(candidate)

    decision = ControlledSelfLearningGate().evaluate(
        failure,
        verification,
        candidate,
        experiment,
        _promotion(experiment),
        _readiness(candidate),
    )

    assert decision.status is SelfLearningCycleStatus.INCONCLUSIVE


def test_locked_evaluation_remains_forbidden_for_p7_experiments() -> None:
    failure = _failure()
    candidate = _candidate(failure)

    with pytest.raises(ValueError, match="locked_evaluation"):
        ExperimentContract(
            experiment_id="EXP-P7-LOCKED",
            candidate_digest=candidate.digest(),
            target_component=candidate.target_component,
            baseline_revision="1" * 40,
            candidate_revision="2" * 40,
            sandbox_id="sandbox-p7",
            allowed_splits=("locked_evaluation",),
            guardrails=(
                MetricGuardrail(
                    name="unsafe_conclusion_rate",
                    direction=MetricDirection.LOWER_IS_BETTER,
                ),
            ),
        )
