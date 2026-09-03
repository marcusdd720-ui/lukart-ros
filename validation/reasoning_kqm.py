"""Measured evaluation of deterministic reasoning behavior."""

from __future__ import annotations

from dataclasses import dataclass

from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningOutcome
from validation.reasoning_gold import ReasoningGoldCorpus, ReasoningGoldSplit

REASONING_KQM_EVALUATOR_VERSION = "reasoning-kqm-v1"


@dataclass(frozen=True, slots=True)
class ReasoningEvaluationFailure:
    case_id: str
    code: str
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class ReasoningKQMMetrics:
    total_cases: int
    correct_decisions: int
    decision_accuracy: float
    expected_conclude: int
    true_conclude: int
    false_conclude: int
    valid_conclusion_recall: float
    expected_abstain: int
    correctly_abstained: int
    abstention_recall: float
    unsafe_conclusion_rate: float
    open_question_coverage: float


@dataclass(frozen=True, slots=True)
class ReasoningKQMReport:
    corpus_id: str
    corpus_version: str
    split: ReasoningGoldSplit
    engine_version: str
    metrics: ReasoningKQMMetrics
    failures: tuple[ReasoningEvaluationFailure, ...]
    result_digests: tuple[tuple[str, str], ...]
    locked_evaluation_executed: bool
    evaluator_version: str = REASONING_KQM_EVALUATOR_VERSION


def _ratio(numerator: int, denominator: int, *, empty_value: float = 1.0) -> float:
    return numerator / denominator if denominator else empty_value


def evaluate_reasoning_split(
    corpus: ReasoningGoldCorpus,
    split: ReasoningGoldSplit,
    *,
    engine_version: str = "reasoning-engine-v1",
    evaluator_version: str = REASONING_KQM_EVALUATOR_VERSION,
    allow_locked: bool = False,
) -> ReasoningKQMReport:
    """Evaluate expected decisions without allowing locked use by default."""

    cases = corpus.cases_for_split(split, allow_locked=allow_locked)
    failures: list[ReasoningEvaluationFailure] = []
    result_digests: list[tuple[str, str]] = []
    correct_decisions = 0
    expected_conclude = 0
    true_conclude = 0
    false_conclude = 0
    expected_abstain = 0
    correctly_abstained = 0
    open_questions_satisfied = 0

    for case in cases:
        result = ReasoningEngine(case.artifacts).evaluate(case.conclusion_id)
        actual = result.decision.outcome
        result_digests.append((case.case_id, result.digest()))

        if case.expected_outcome is ReasoningOutcome.CONCLUDE:
            expected_conclude += 1
            if actual is ReasoningOutcome.CONCLUDE:
                true_conclude += 1
        else:
            expected_abstain += 1
            if actual is ReasoningOutcome.ABSTAIN:
                correctly_abstained += 1
            if actual is ReasoningOutcome.CONCLUDE:
                false_conclude += 1
            if len(result.open_questions) >= case.expected_min_open_questions:
                open_questions_satisfied += 1

        if actual is case.expected_outcome:
            correct_decisions += 1
        else:
            failures.append(
                ReasoningEvaluationFailure(
                    case_id=case.case_id,
                    code="DECISION_MISMATCH",
                    expected=case.expected_outcome.value,
                    actual=actual.value,
                )
            )

        if (
            case.expected_outcome is ReasoningOutcome.ABSTAIN
            and len(result.open_questions) < case.expected_min_open_questions
        ):
            failures.append(
                ReasoningEvaluationFailure(
                    case_id=case.case_id,
                    code="OPEN_QUESTION_COVERAGE",
                    expected=f">={case.expected_min_open_questions}",
                    actual=str(len(result.open_questions)),
                )
            )

    total = len(cases)
    metrics = ReasoningKQMMetrics(
        total_cases=total,
        correct_decisions=correct_decisions,
        decision_accuracy=_ratio(correct_decisions, total),
        expected_conclude=expected_conclude,
        true_conclude=true_conclude,
        false_conclude=false_conclude,
        valid_conclusion_recall=_ratio(true_conclude, expected_conclude),
        expected_abstain=expected_abstain,
        correctly_abstained=correctly_abstained,
        abstention_recall=_ratio(correctly_abstained, expected_abstain),
        unsafe_conclusion_rate=_ratio(false_conclude, expected_abstain, empty_value=0.0),
        open_question_coverage=_ratio(open_questions_satisfied, expected_abstain),
    )
    return ReasoningKQMReport(
        corpus_id=corpus.corpus_id,
        corpus_version=corpus.version,
        split=split,
        engine_version=engine_version,
        metrics=metrics,
        failures=tuple(failures),
        result_digests=tuple(result_digests),
        locked_evaluation_executed=split is ReasoningGoldSplit.LOCKED_EVALUATION,
        evaluator_version=evaluator_version,
    )
