from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from learning import (
    ChangeKind,
    ExperimentMeasurement,
    ExperimentResult,
    LockedLearningSourceError,
    MetricDirection,
    MetricGuardrail,
    MetricValue,
    PromotionGate,
    PromotionStatus,
    candidate_from_failure,
    contract_for_candidate,
    failure_corpus_from_reasoning,
)
from validation.reasoning_gold import ReasoningGoldSplit
from validation.reasoning_kqm import (
    ReasoningEvaluationFailure,
    ReasoningKQMMetrics,
    ReasoningKQMReport,
)

SOURCE_SHA = "1" * 40
RESULT_DIGEST = "2" * 64


def _metrics() -> ReasoningKQMMetrics:
    return ReasoningKQMMetrics(
        total_cases=1,
        correct_decisions=0,
        decision_accuracy=0.0,
        expected_conclude=1,
        true_conclude=0,
        false_conclude=0,
        valid_conclusion_recall=0.0,
        expected_abstain=0,
        correctly_abstained=0,
        abstention_recall=1.0,
        unsafe_conclusion_rate=0.0,
        open_question_coverage=1.0,
    )


def _report(
    *,
    split: ReasoningGoldSplit = ReasoningGoldSplit.DEVELOPMENT,
    locked: bool = False,
    result_digests: tuple[tuple[str, str], ...] = (("SYN-R-FAIL", RESULT_DIGEST),),
) -> ReasoningKQMReport:
    return ReasoningKQMReport(
        corpus_id="reasoning-gold-v1",
        corpus_version="1.0.0",
        split=split,
        engine_version="reasoning-engine-v1",
        evaluator_version="reasoning-kqm-v1",
        metrics=_metrics(),
        failures=(
            ReasoningEvaluationFailure(
                case_id="SYN-R-FAIL",
                code="DECISION_MISMATCH",
                expected="conclude",
                actual="abstain",
            ),
        ),
        result_digests=result_digests,
        locked_evaluation_executed=locked,
    )


def _candidate():
    corpus = failure_corpus_from_reasoning(_report(), source_sha=SOURCE_SHA)
    failure = corpus.failures[0]
    return candidate_from_failure(
        failure,
        target_component="reasoning.engine",
        change_kind=ChangeKind.RULE,
        hypothesis="Require a validated support path before conclusion selection.",
        success_criteria=(
            "decision_accuracy must improve",
            "unsafe_conclusion_rate must not regress",
        ),
    )


def _contract():
    candidate = _candidate()
    return contract_for_candidate(
        candidate,
        experiment_id="EXP-P4-001",
        baseline_revision="baseline-a",
        candidate_revision="candidate-b",
        sandbox_id="sandbox-p4",
        allowed_splits=("development", "validation"),
        guardrails=(
            MetricGuardrail(
                name="decision_accuracy",
                direction=MetricDirection.HIGHER_IS_BETTER,
            ),
            MetricGuardrail(
                name="unsafe_conclusion_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
            ),
        ),
        max_runs=2,
    )


def _result(
    *,
    decision_accuracy: float,
    unsafe_conclusion_rate: float,
    run_count: int = 1,
    contract_digest: str | None = None,
) -> ExperimentResult:
    contract = _contract()
    return ExperimentResult(
        contract_digest=contract_digest or contract.digest(),
        baseline=ExperimentMeasurement(
            revision=contract.baseline_revision,
            metrics=(
                MetricValue("decision_accuracy", 0.5),
                MetricValue("unsafe_conclusion_rate", 0.1),
            ),
        ),
        candidate=ExperimentMeasurement(
            revision=contract.candidate_revision,
            metrics=(
                MetricValue("decision_accuracy", decision_accuracy),
                MetricValue("unsafe_conclusion_rate", unsafe_conclusion_rate),
            ),
        ),
        run_count=run_count,
    )


def test_failure_corpus_preserves_measurement_provenance() -> None:
    report = _report()
    corpus = failure_corpus_from_reasoning(report, source_sha=SOURCE_SHA)

    assert corpus.corpus_id == "failure-reasoning-gold-v1-development"
    assert len(corpus.failures) == 1
    failure = corpus.failures[0]
    assert failure.case_id == "SYN-R-FAIL"
    assert failure.source_sha == SOURCE_SHA
    assert failure.result_digest == RESULT_DIGEST
    assert failure.evaluator_version == "reasoning-kqm-v1"
    assert len(failure.report_digest) == 64
    assert len(failure.digest()) == 64


def test_locked_reasoning_output_cannot_become_learning_input() -> None:
    report = _report(
        split=ReasoningGoldSplit.LOCKED_EVALUATION,
        locked=True,
    )

    with pytest.raises(LockedLearningSourceError, match="locked evaluation"):
        failure_corpus_from_reasoning(report, source_sha=SOURCE_SHA)


def test_learning_input_requires_case_result_digest() -> None:
    with pytest.raises(ValueError, match="lacks result digest"):
        failure_corpus_from_reasoning(
            _report(result_digests=()),
            source_sha=SOURCE_SHA,
        )


def test_learning_candidate_is_deterministic_traceable_and_immutable() -> None:
    candidate = _candidate()
    repeated = _candidate()

    assert candidate.candidate_id == repeated.candidate_id
    assert candidate.digest() == repeated.digest()
    assert len(candidate.source_failure_digest) == 64
    with pytest.raises(FrozenInstanceError):
        candidate.hypothesis = "silent mutation"  # type: ignore[misc]


def test_experiment_rejects_locked_and_unknown_splits() -> None:
    candidate = _candidate()
    guardrail = (
        MetricGuardrail("decision_accuracy", MetricDirection.HIGHER_IS_BETTER),
    )

    for forbidden_split in ("locked_evaluation", "production", "test"):
        with pytest.raises(ValueError, match="unsupported learning experiment split"):
            contract_for_candidate(
                candidate,
                experiment_id="EXP-P4-SPLIT",
                baseline_revision="baseline-a",
                candidate_revision="candidate-b",
                sandbox_id="sandbox-p4",
                allowed_splits=(forbidden_split,),
                guardrails=guardrail,
            )


def test_experiment_requires_distinct_revisions() -> None:
    candidate = _candidate()
    with pytest.raises(ValueError, match="must differ"):
        contract_for_candidate(
            candidate,
            experiment_id="EXP-P4-REV",
            baseline_revision="same",
            candidate_revision="same",
            sandbox_id="sandbox-p4",
            allowed_splits=("development",),
            guardrails=(
                MetricGuardrail("decision_accuracy", MetricDirection.HIGHER_IS_BETTER),
            ),
        )


def test_metric_contracts_reject_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        MetricValue("decision_accuracy", float("nan"))
    with pytest.raises(ValueError, match="finite"):
        MetricGuardrail(
            "decision_accuracy",
            MetricDirection.HIGHER_IS_BETTER,
            max_regression=float("inf"),
        )


def test_promotion_gate_marks_improvement_eligible_without_mutation_authority() -> None:
    contract = _contract()
    result = _result(decision_accuracy=0.75, unsafe_conclusion_rate=0.05)

    decision = PromotionGate().evaluate(contract, result)

    assert decision.status is PromotionStatus.ELIGIBLE_FOR_PROMOTION
    assert decision.contract_digest == contract.digest()
    assert len(decision.deltas) == 2


def test_promotion_gate_rejects_guardrail_regression() -> None:
    contract = _contract()
    result = _result(decision_accuracy=0.75, unsafe_conclusion_rate=0.2)

    decision = PromotionGate().evaluate(contract, result)

    assert decision.status is PromotionStatus.REJECTED
    assert "unsafe_conclusion_rate" in decision.reason


def test_promotion_gate_marks_no_improvement_inconclusive() -> None:
    contract = _contract()
    result = _result(decision_accuracy=0.5, unsafe_conclusion_rate=0.1)

    decision = PromotionGate().evaluate(contract, result)

    assert decision.status is PromotionStatus.INCONCLUSIVE


def test_promotion_gate_rejects_wrong_contract_and_run_budget() -> None:
    contract = _contract()
    wrong_contract_result = _result(
        decision_accuracy=0.75,
        unsafe_conclusion_rate=0.05,
        contract_digest="f" * 64,
    )
    over_budget = _result(
        decision_accuracy=0.75,
        unsafe_conclusion_rate=0.05,
        run_count=3,
    )

    assert PromotionGate().evaluate(contract, wrong_contract_result).status is PromotionStatus.REJECTED
    assert PromotionGate().evaluate(contract, over_budget).status is PromotionStatus.REJECTED
