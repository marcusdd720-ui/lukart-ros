from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from agents.certification import (
    AgentCertificationThresholds,
    AgentCertifier,
)
from agents.reference_fact import ReferenceFactAgent
from learning.candidates import candidate_from_failure
from learning.experiment import (
    ExperimentMeasurement,
    ExperimentResult,
    MetricDirection,
    MetricGuardrail,
    contract_for_candidate,
)
from learning.models import ChangeKind, LearningSource, MeasuredFailure, MetricValue
from learning.promotion import PromotionDecision, PromotionGate, PromotionStatus
from learning.teaching import (
    AgentTeachingReleaseGate,
    TeachingApproval,
    TeachingExampleKind,
    TeachingReleaseStatus,
    distill_agent_teaching_package,
    failure_teaching_example,
    gold_teaching_example,
)
from validation.extraction_quality import ExtractionMetrics
from validation.independent_evaluation import ReviewOutcome


def _failure() -> MeasuredFailure:
    return MeasuredFailure(
        failure_id="P5-F-001",
        source=LearningSource.REASONING_KQM,
        corpus_id="reasoning-gold-v1",
        corpus_version="1.0.0",
        split="development",
        evaluator_version="reasoning-kqm-v1",
        source_sha="a" * 40,
        case_id="SYN-P5-001",
        code="DECISION_MISMATCH",
        expected="conclude",
        actual="abstain",
        result_digest="b" * 64,
        report_digest="c" * 64,
    )


def _p4_bundle(
    change_kind: ChangeKind = ChangeKind.RULE,
) -> tuple[MeasuredFailure, object, object, PromotionDecision]:
    failure = _failure()
    target_name = ReferenceFactAgent().contract.name
    candidate = candidate_from_failure(
        failure,
        target_component=target_name,
        change_kind=change_kind,
        hypothesis="Use the reviewed example to reduce this measured failure mode.",
        success_criteria=("decision_accuracy improves",),
    )
    contract = contract_for_candidate(
        candidate,
        experiment_id="P5-EXP-001",
        baseline_revision="baseline-v1",
        candidate_revision="candidate-v2",
        sandbox_id="p5-sandbox",
        allowed_splits=("development", "validation"),
        guardrails=(
            MetricGuardrail(
                name="decision_accuracy",
                direction=MetricDirection.HIGHER_IS_BETTER,
            ),
        ),
        max_runs=2,
    )
    result = ExperimentResult(
        contract_digest=contract.digest(),
        baseline=ExperimentMeasurement(
            revision="baseline-v1",
            metrics=(MetricValue("decision_accuracy", 0.50),),
        ),
        candidate=ExperimentMeasurement(
            revision="candidate-v2",
            metrics=(MetricValue("decision_accuracy", 0.80),),
        ),
        run_count=1,
    )
    decision = PromotionGate().evaluate(contract, result)
    return failure, candidate, contract, decision


def _failure_example() -> object:
    return failure_teaching_example(
        _failure(),
        input_digest="d" * 64,
        expected_output_digest="e" * 64,
        evidence_digests=("f" * 64,),
    )


def _approval(example: object, outcome: ReviewOutcome = ReviewOutcome.PASS) -> TeachingApproval:
    return TeachingApproval(
        example_digest=example.digest(),  # type: ignore[attr-defined]
        reviewer_id="external-reviewer-p5",
        outcome=outcome,
        rationale="Example independently checked against its evidence.",
        evidence_ref="review:P5-001",
    )


def _package(change_kind: ChangeKind = ChangeKind.RULE):
    _, candidate, contract, decision = _p4_bundle(change_kind)
    example = _failure_example()
    package = distill_agent_teaching_package(
        candidate,  # type: ignore[arg-type]
        contract,  # type: ignore[arg-type]
        decision,
        ReferenceFactAgent().contract,
        package_version="1.0.0",
        teaching_instruction="Apply only the reviewed pattern represented by this manifest.",
        examples=(example,),  # type: ignore[arg-type]
        approvals=(_approval(example),),
    )
    return package, example


def _metrics() -> ExtractionMetrics:
    return ExtractionMetrics(
        true_positive=10,
        false_positive=0,
        false_negative=0,
        precision=1.0,
        recall=1.0,
        f1=1.0,
        critical_true_positive=5,
        critical_false_positive=0,
        critical_false_negative=0,
        critical_recall=1.0,
        critical_precision=1.0,
        critical_fact_loss=0,
        case_number_false_positive_rate=0.0,
        provenance_completeness=1.0,
    )


def _certifier() -> AgentCertifier:
    return AgentCertifier(
        AgentCertificationThresholds(
            min_precision=0.95,
            min_recall=0.90,
            min_f1=0.92,
            min_critical_recall=0.95,
        )
    )


def test_gold_example_is_digest_bound_deterministic_and_immutable() -> None:
    kwargs = {
        "example_id": "GOLD-P5-001",
        "corpus_id": "agent-teaching-gold-v1",
        "corpus_version": "1.0.0",
        "split": "validation",
        "source_ref": "gold:GOLD-P5-001",
        "source_digest": "a" * 64,
        "input_digest": "b" * 64,
        "expected_output_digest": "c" * 64,
        "evidence_digests": ("d" * 64,),
    }
    first = gold_teaching_example(**kwargs)  # type: ignore[arg-type]
    second = gold_teaching_example(**kwargs)  # type: ignore[arg-type]

    assert first.kind is TeachingExampleKind.GOLD
    assert first.digest() == second.digest()
    with pytest.raises(FrozenInstanceError):
        first.split = "development"  # type: ignore[misc]


@pytest.mark.parametrize("split", ["locked_evaluation", "production", "test"])
def test_teaching_examples_reject_non_learning_splits(split: str) -> None:
    with pytest.raises(ValueError, match="unsupported teaching split"):
        gold_teaching_example(
            example_id="GOLD-P5-BLOCKED",
            corpus_id="agent-teaching-gold-v1",
            corpus_version="1.0.0",
            split=split,
            source_ref="gold:GOLD-P5-BLOCKED",
            source_digest="a" * 64,
            input_digest="b" * 64,
            expected_output_digest="c" * 64,
            evidence_digests=("d" * 64,),
        )


def test_failure_example_preserves_measured_failure_provenance() -> None:
    failure = _failure()
    example = failure_teaching_example(
        failure,
        input_digest="d" * 64,
        expected_output_digest="e" * 64,
        evidence_digests=("f" * 64,),
    )

    assert example.kind is TeachingExampleKind.FAILURE
    assert example.source_digest == failure.digest()
    assert example.source_corpus_id == failure.corpus_id
    assert example.source_corpus_version == failure.corpus_version
    assert example.split == failure.split


def test_approval_rejects_automated_reviewer_identity() -> None:
    example = _failure_example()
    with pytest.raises(ValueError, match="independent reviewer"):
        TeachingApproval(
            example_digest=example.digest(),  # type: ignore[attr-defined]
            reviewer_id="factory",
            outcome=ReviewOutcome.PASS,
            rationale="Synthetic automation must not approve teaching truth.",
            evidence_ref="review:blocked",
        )


def test_distillation_requires_eligible_p4_decision() -> None:
    _, candidate, contract, decision = _p4_bundle()
    example = _failure_example()
    rejected = replace(decision, status=PromotionStatus.REJECTED)

    with pytest.raises(ValueError, match="ELIGIBLE_FOR_PROMOTION"):
        distill_agent_teaching_package(
            candidate,  # type: ignore[arg-type]
            contract,  # type: ignore[arg-type]
            rejected,
            ReferenceFactAgent().contract,
            package_version="1.0.0",
            teaching_instruction="Do not bypass the P4 promotion gate.",
            examples=(example,),  # type: ignore[arg-type]
            approvals=(_approval(example),),
        )


def test_distillation_rejects_non_pass_or_incomplete_example_approval() -> None:
    _, candidate, contract, decision = _p4_bundle()
    example = _failure_example()

    with pytest.raises(ValueError, match="independent PASS"):
        distill_agent_teaching_package(
            candidate,  # type: ignore[arg-type]
            contract,  # type: ignore[arg-type]
            decision,
            ReferenceFactAgent().contract,
            package_version="1.0.0",
            teaching_instruction="Use only independently approved examples.",
            examples=(example,),  # type: ignore[arg-type]
            approvals=(_approval(example, ReviewOutcome.FAIL),),
        )

    with pytest.raises(ValueError, match="exactly cover"):
        distill_agent_teaching_package(
            candidate,  # type: ignore[arg-type]
            contract,  # type: ignore[arg-type]
            decision,
            ReferenceFactAgent().contract,
            package_version="1.0.0",
            teaching_instruction="Missing approval must fail closed.",
            examples=(example,),  # type: ignore[arg-type]
            approvals=(),
        )


def test_distillation_rejects_candidate_contract_or_decision_mismatch() -> None:
    _, candidate, contract, decision = _p4_bundle()
    example = _failure_example()
    bad_decision = replace(decision, contract_digest="a" * 64)

    with pytest.raises(ValueError, match="promotion decision is not bound"):
        distill_agent_teaching_package(
            candidate,  # type: ignore[arg-type]
            contract,  # type: ignore[arg-type]
            bad_decision,
            ReferenceFactAgent().contract,
            package_version="1.0.0",
            teaching_instruction="All P4 provenance links must match.",
            examples=(example,),  # type: ignore[arg-type]
            approvals=(_approval(example),),
        )


@pytest.mark.parametrize("change_kind", [ChangeKind.CODE, ChangeKind.POLICY, ChangeKind.ROUTING])
def test_p5_rejects_non_distillation_change_kinds(change_kind: ChangeKind) -> None:
    _, candidate, contract, decision = _p4_bundle(change_kind)
    example = _failure_example()

    with pytest.raises(ValueError, match="P5 cannot distill"):
        distill_agent_teaching_package(
            candidate,  # type: ignore[arg-type]
            contract,  # type: ignore[arg-type]
            decision,
            ReferenceFactAgent().contract,
            package_version="1.0.0",
            teaching_instruction="Code, policy, and routing require different promotion paths.",
            examples=(example,),  # type: ignore[arg-type]
            approvals=(_approval(example),),
        )


def test_package_is_deterministic_contract_bound_and_has_no_mutation_api() -> None:
    first, _ = _package()
    second, _ = _package()

    assert first.package_id == second.package_id
    assert first.digest() == second.digest()
    assert first.target_agent_name == ReferenceFactAgent().contract.name
    assert not hasattr(first, "apply")
    assert not hasattr(first, "promote")
    assert not hasattr(first, "mutate")
    with pytest.raises(FrozenInstanceError):
        first.package_version = "2.0.0"  # type: ignore[misc]


def test_release_gate_requires_exact_recertification() -> None:
    package, _ = _package()
    contract = ReferenceFactAgent().contract
    pending = _certifier().evaluate(
        contract,
        _metrics(),
        corpus_version="agent-teaching-gold-v1",
        split_name="validation",
    )
    certified = _certifier().evaluate(
        contract,
        _metrics(),
        corpus_version="agent-teaching-gold-v1",
        split_name="validation",
        external_review=ReviewOutcome.PASS,
    )
    gate = AgentTeachingReleaseGate()

    assert gate.evaluate(package, pending).status is TeachingReleaseStatus.PENDING_RECERTIFICATION
    assert gate.evaluate(package, certified).status is TeachingReleaseStatus.ELIGIBLE_FOR_RELEASE

    mismatched = replace(certified, agent_version="99.0.0")
    assert gate.evaluate(package, mismatched).status is TeachingReleaseStatus.REJECTED
