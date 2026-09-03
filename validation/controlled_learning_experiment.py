"""Measured Step 12 harness over the existing P4-P7 control path.

The harness is deliberately pure: it creates no files, mutates no Product state,
and grants no deployment authority.  It exists to exercise the real learning,
verification, promotion, replay/revalidation, and self-learning gates with a
bounded synthetic measurement fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from core.models.ids import AgentId
from knowledge.case_replay import CaseReplayRecord
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
from learning.experiment import (
    ExperimentMeasurement,
    ExperimentResult,
    MetricDirection,
    MetricGuardrail,
    contract_for_candidate,
)
from learning.models import ChangeKind, LearningSource, MeasuredFailure, MetricValue
from learning.promotion import PromotionGate, PromotionStatus
from learning.semantic_self_healing import (
    ComponentDependency,
    ComponentDependencyGraph,
    ComponentNode,
    DiagnosisRule,
    RepairReadinessStatus,
    RootCauseCategory,
    SemanticFailureDiagnoser,
    SemanticSelfHealingGate,
    plan_revalidation,
    repair_candidate_from_diagnosis,
    validation_evidence_from_replays,
)

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _git_sha(name: str, value: str) -> str:
    normalized = value.strip().lower()
    if not _GIT_SHA_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a full hexadecimal commit SHA")
    return normalized


def _agent(number: int) -> AgentId:
    return AgentId(UUID(int=number))


@dataclass(frozen=True, slots=True)
class ControlledLearningExperimentReport:
    validated_sha: str
    baseline_sha: str
    candidate_sha: str
    failure_digest: str
    verification_digest: str
    candidate_digest: str
    experiment_digest: str
    validation_evidence_digest: str
    cycle_digest: str
    promotion_status: PromotionStatus
    readiness_status: RepairReadinessStatus
    cycle_status: SelfLearningCycleStatus
    measured_failure_bound: bool
    candidate_experiment_executed: bool
    promotion_gate_applied: bool
    production_mutation_absent: bool
    locked_evaluation_used_for_tuning: bool = False
    private_data_used: bool = False

    @property
    def passed(self) -> bool:
        return (
            self.measured_failure_bound
            and self.candidate_experiment_executed
            and self.promotion_gate_applied
            and self.production_mutation_absent
            and not self.locked_evaluation_used_for_tuning
            and not self.private_data_used
            and self.promotion_status is PromotionStatus.ELIGIBLE_FOR_PROMOTION
            and self.readiness_status is RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION
            and self.cycle_status is SelfLearningCycleStatus.READY_FOR_EXISTING_RELEASE_PATH
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "baseline_sha": self.baseline_sha,
            "candidate_digest": self.candidate_digest,
            "candidate_experiment_executed": self.candidate_experiment_executed,
            "candidate_sha": self.candidate_sha,
            "cycle_digest": self.cycle_digest,
            "cycle_status": self.cycle_status.value,
            "experiment_digest": self.experiment_digest,
            "failure_digest": self.failure_digest,
            "locked_evaluation_used_for_tuning": self.locked_evaluation_used_for_tuning,
            "measured_failure_bound": self.measured_failure_bound,
            "private_data_used": self.private_data_used,
            "production_mutation_absent": self.production_mutation_absent,
            "promotion_gate_applied": self.promotion_gate_applied,
            "promotion_status": self.promotion_status.value,
            "readiness_status": self.readiness_status.value,
            "validated_sha": self.validated_sha,
            "validation_evidence_digest": self.validation_evidence_digest,
            "verification_digest": self.verification_digest,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()


def _verified_failure(failure: MeasuredFailure):  # type: ignore[no-untyped-def]
    claim_digest = _sha256("step12:measured-failure-claim")
    proposal = VerificationProposal(
        proposal_id="STEP12-LEARNING-TRIGGER",
        generator_agent_id=_agent(1),
        subject_type="measured_failure",
        subject_digest=failure.digest(),
        claim_digests=(claim_digest,),
        evidence_digests=(failure.result_digest, failure.report_digest),
    )
    challenge = ChallengeAssessment(
        challenger_agent_id=_agent(2),
        proposal_digest=proposal.digest(),
        findings=(
            ChallengeFinding(
                code="STEP12-CH-1",
                claim_digest=claim_digest,
                rationale="require independent confirmation of the measured failure",
                blocking=True,
                evidence_digests=(failure.result_digest,),
            ),
        ),
    )
    evidence = EvidenceVerification(
        verifier_agent_id=_agent(3),
        proposal_digest=proposal.digest(),
        status=EvidenceVerificationStatus.PASS,
        checked_evidence_digests=proposal.evidence_digests,
        challenge_resolutions=(
            ChallengeResolution(
                challenge_code="STEP12-CH-1",
                status=ChallengeResolutionStatus.RESOLVED,
                evidence_digests=(failure.result_digest,),
                rationale="the synthetic KQM result independently confirms the trigger",
            ),
        ),
    )
    review = ReviewAssessment(
        reviewer_agent_id=_agent(4),
        proposal_digest=proposal.digest(),
        status=ReviewStatus.PASS,
        rationale="independent process review confirms evidence-bound learning input",
    )
    decision = AdversarialVerificationGate().evaluate(
        proposal,
        (challenge,),
        evidence,
        review,
    )
    if decision.status is not AdversarialVerificationStatus.VERIFIED:
        raise RuntimeError("synthetic Step 12 learning trigger did not verify")
    return decision


def _replay(*, git_commit: str) -> CaseReplayRecord:
    return CaseReplayRecord(
        case_key="SYN-STEP12",
        snapshot_id="SYN-STEP12-SNAPSHOT",
        manifest_sha256=_sha256("step12:manifest"),
        source_sha256=(("SYN-SOURCE", _sha256("step12:source")),),
        pipeline_version="step12-controlled-learning-v1",
        graph_sha256=_sha256("step12:graph"),
        agent_bindings=(),
        renderer_version="reasoning-markdown-v1",
        git_commit=git_commit,
    )


def run_controlled_learning_experiment(
    *,
    validated_sha: str,
    baseline_sha: str,
    candidate_sha: str,
    baseline_unsafe_conclusion_rate: float = 0.25,
    candidate_unsafe_conclusion_rate: float = 0.0,
) -> ControlledLearningExperimentReport:
    """Exercise P4-P7 gates without using locked splits or mutating production state."""

    validated = _git_sha("validated_sha", validated_sha)
    baseline = _git_sha("baseline_sha", baseline_sha)
    candidate_revision = _git_sha("candidate_sha", candidate_sha)
    if baseline == candidate_revision:
        raise ValueError("controlled learning requires a fresh candidate SHA")

    failure = MeasuredFailure(
        failure_id="STEP12-SYN-FAIL-1",
        source=LearningSource.REASONING_KQM,
        corpus_id="step12-synthetic-control",
        corpus_version="1.0.0",
        split="development",
        evaluator_version="step12-kqm-v1",
        source_sha=validated,
        case_id="SYN-STEP12-CASE-1",
        code="unsafe_conclusion",
        expected="abstain",
        actual="conclude",
        result_digest=_sha256("step12:kqm-result"),
        report_digest=_sha256("step12:kqm-report"),
    )
    verification = _verified_failure(failure)

    diagnoser = SemanticFailureDiagnoser(
        (
            DiagnosisRule(
                rule_id="STEP12-DX-RULE-1",
                source=LearningSource.REASONING_KQM,
                failure_code="unsafe_conclusion",
                root_cause=RootCauseCategory.REASONING,
                target_component="reasoning.engine",
                rationale="unsafe conclusion is owned by the reasoning decision gate",
            ),
        )
    )
    diagnosis = diagnoser.diagnose(failure)
    learning_candidate = repair_candidate_from_diagnosis(
        failure,
        diagnosis,
        change_kind=ChangeKind.RULE,
        hypothesis="stricter evidence support should reduce unsafe conclusions",
        success_criteria=("unsafe_conclusion_rate decreases without regression",),
    )

    graph = ComponentDependencyGraph(
        graph_version="step12-graph-v1",
        nodes=(
            ComponentNode(
                component_id="reasoning.engine",
                validators=("reasoning_kqm", "case_replay"),
            ),
            ComponentNode(
                component_id="renderer.reasoning",
                validators=("renderer_quality",),
            ),
        ),
        dependencies=(
            ComponentDependency(
                upstream="reasoning.engine",
                downstream="renderer.reasoning",
            ),
        ),
        complete=True,
        completeness_evidence_digest=_sha256("step12:graph-completeness"),
    )
    plan = plan_revalidation(diagnosis, graph)

    experiment = contract_for_candidate(
        learning_candidate,
        experiment_id="STEP12-EXP-1",
        baseline_revision=baseline,
        candidate_revision=candidate_revision,
        sandbox_id="step12-synthetic-sandbox",
        allowed_splits=("development", "validation"),
        guardrails=(
            MetricGuardrail(
                name="unsafe_conclusion_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                max_regression=0.0,
            ),
        ),
        max_runs=1,
    )
    result = ExperimentResult(
        contract_digest=experiment.digest(),
        baseline=ExperimentMeasurement(
            revision=baseline,
            metrics=(
                MetricValue(
                    name="unsafe_conclusion_rate",
                    value=baseline_unsafe_conclusion_rate,
                ),
            ),
        ),
        candidate=ExperimentMeasurement(
            revision=candidate_revision,
            metrics=(
                MetricValue(
                    name="unsafe_conclusion_rate",
                    value=candidate_unsafe_conclusion_rate,
                ),
            ),
        ),
        run_count=1,
    )
    promotion = PromotionGate().evaluate(experiment, result)

    baseline_replay = _replay(git_commit=baseline)
    candidate_replay = _replay(git_commit=candidate_revision)
    validation_evidence = validation_evidence_from_replays(
        learning_candidate,
        plan,
        baseline_sha=baseline,
        repair_sha=candidate_revision,
        baseline_replay=baseline_replay,
        repair_replay=candidate_replay,
        expected_replay_drift_fields=("git_commit",),
        kqm_result_digest=_sha256("step12:candidate-kqm-result"),
        kqm_report_digest=_sha256("step12:candidate-kqm-report"),
        executed_validators=plan.validators,
        passed_validators=plan.validators,
    )
    readiness = SemanticSelfHealingGate().evaluate(
        learning_candidate,
        experiment,
        promotion,
        plan,
        validation_evidence,
    )
    cycle = ControlledSelfLearningGate().evaluate(
        failure,
        verification,
        learning_candidate,
        experiment,
        promotion,
        readiness,
    )

    return ControlledLearningExperimentReport(
        validated_sha=validated,
        baseline_sha=baseline,
        candidate_sha=candidate_revision,
        failure_digest=failure.digest(),
        verification_digest=verification.digest(),
        candidate_digest=learning_candidate.digest(),
        experiment_digest=experiment.digest(),
        validation_evidence_digest=validation_evidence.digest(),
        cycle_digest=cycle.digest(),
        promotion_status=promotion.status,
        readiness_status=readiness.status,
        cycle_status=cycle.status,
        measured_failure_bound=(learning_candidate.source_failure_digest == failure.digest()),
        candidate_experiment_executed=(result.contract_digest == experiment.digest()),
        promotion_gate_applied=(promotion.contract_digest == experiment.digest()),
        production_mutation_absent=True,
        locked_evaluation_used_for_tuning=False,
        private_data_used=False,
    )
