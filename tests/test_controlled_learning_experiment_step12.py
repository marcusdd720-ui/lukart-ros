from __future__ import annotations

import pytest

from learning.controlled_self_learning import SelfLearningCycleStatus
from learning.promotion import PromotionStatus
from learning.semantic_self_healing import RepairReadinessStatus
from validation.controlled_learning_experiment import run_controlled_learning_experiment


def test_step12_exercises_full_controlled_learning_path_without_mutation() -> None:
    report = run_controlled_learning_experiment(
        validated_sha="a" * 40,
        baseline_sha="b" * 40,
        candidate_sha="c" * 40,
    )

    assert report.passed is True
    assert report.measured_failure_bound is True
    assert report.candidate_experiment_executed is True
    assert report.promotion_gate_applied is True
    assert report.production_mutation_absent is True
    assert report.locked_evaluation_used_for_tuning is False
    assert report.private_data_used is False
    assert report.promotion_status is PromotionStatus.ELIGIBLE_FOR_PROMOTION
    assert report.readiness_status is RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION
    assert report.cycle_status is SelfLearningCycleStatus.READY_FOR_EXISTING_RELEASE_PATH
    assert len(report.digest()) == 64


def test_step12_regression_is_rejected_by_existing_promotion_path() -> None:
    report = run_controlled_learning_experiment(
        validated_sha="a" * 40,
        baseline_sha="b" * 40,
        candidate_sha="c" * 40,
        baseline_unsafe_conclusion_rate=0.10,
        candidate_unsafe_conclusion_rate=0.25,
    )

    assert report.passed is False
    assert report.promotion_status is PromotionStatus.REJECTED
    assert report.readiness_status is RepairReadinessStatus.REJECTED
    assert report.cycle_status is SelfLearningCycleStatus.SUSPENDED


def test_step12_requires_a_fresh_candidate_sha() -> None:
    with pytest.raises(ValueError, match="fresh candidate SHA"):
        run_controlled_learning_experiment(
            validated_sha="a" * 40,
            baseline_sha="b" * 40,
            candidate_sha="b" * 40,
        )


def test_step12_rejects_non_sha_provenance() -> None:
    with pytest.raises(ValueError, match="validated_sha"):
        run_controlled_learning_experiment(
            validated_sha="not-a-sha",
            baseline_sha="b" * 40,
            candidate_sha="c" * 40,
        )
