import pytest

from validation.independent_evaluation import (
    IndependentEvaluationError,
    IndependentEvaluator,
    ReviewerAssessment,
    ReviewOutcome,
)
from validation.measurement import MeasurementSnapshot
MEASUREMENTS = MeasurementSnapshot({"precision": 0.95, "recall": 0.9})


def test_external_review_is_recorded_without_modifying_measurements() -> None:
    assessment = ReviewerAssessment(
        reviewer_id="reviewer-1",
        outcome=ReviewOutcome.PASS,
        rationale="Reviewed against the locked evaluation protocol.",
        evidence_ref="review://case-001",
    )

    record = IndependentEvaluator().record(MEASUREMENTS, assessment)

    assert record.measurements is MEASUREMENTS
    assert record.assessment is assessment


def test_automated_reviewer_identity_is_rejected() -> None:
    assessment = ReviewerAssessment(
        reviewer_id="automated",
        outcome=ReviewOutcome.PASS,
        rationale="synthetic",
        evidence_ref="review://case-002",
    )

    with pytest.raises(IndependentEvaluationError, match="external reviewer"):
        IndependentEvaluator().record(MEASUREMENTS, assessment)


def test_pending_outcome_is_rejected() -> None:
    assessment = ReviewerAssessment(
        reviewer_id="reviewer-2",
        outcome=ReviewOutcome.PENDING,
        rationale="awaiting review",
        evidence_ref="review://case-003",
    )

    with pytest.raises(IndependentEvaluationError, match="PASS or FAIL"):
        IndependentEvaluator().record(MEASUREMENTS, assessment)


def test_missing_rationale_and_evidence_are_rejected() -> None:
    evaluator = IndependentEvaluator()
    for assessment in (
        ReviewerAssessment("reviewer-3", ReviewOutcome.FAIL, "", "review://case-004"),
        ReviewerAssessment("reviewer-3", ReviewOutcome.FAIL, "reason", ""),
    ):
        with pytest.raises(IndependentEvaluationError):
            evaluator.record(MEASUREMENTS, assessment)
