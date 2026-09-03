from __future__ import annotations

from pathlib import Path

import pytest

from validation.e2e_gold import (
    EndToEndGoldSplit,
    LockedEndToEndEvaluationError,
    evaluate_e2e_split,
    load_e2e_gold_corpus,
)

CORPUS_PATH = Path("data/quality/e2e_gold_v1.json")


def test_e2e_gold_corpus_has_sealed_partition() -> None:
    corpus = load_e2e_gold_corpus(CORPUS_PATH)

    assert corpus.corpus_id == "e2e-gold-v1"
    assert len(corpus.cases_for_split(EndToEndGoldSplit.DEVELOPMENT)) == 4
    assert len(corpus.cases_for_split(EndToEndGoldSplit.VALIDATION)) == 2

    with pytest.raises(LockedEndToEndEvaluationError, match="locked E2E evaluation"):
        corpus.cases_for_split(EndToEndGoldSplit.LOCKED_EVALUATION)


def test_e2e_development_loop_passes_without_fact_promotion() -> None:
    corpus = load_e2e_gold_corpus(CORPUS_PATH)
    report = evaluate_e2e_split(corpus, EndToEndGoldSplit.DEVELOPMENT)

    assert report.passed is True
    assert report.metrics.total_cases == 4
    assert report.metrics.passed_cases == 4
    assert report.metrics.agent_acceptance_rate == 1.0
    assert report.metrics.extraction_expectation_accuracy == 1.0
    assert report.metrics.reasoning_decision_accuracy == 1.0
    assert report.metrics.renderer_quality_rate == 1.0
    assert report.metrics.unsafe_fact_promotion_count == 0
    assert report.locked_evaluation_executed is False
    assert len(report.digest()) == 64


def test_e2e_validation_loop_passes_without_locked_execution() -> None:
    corpus = load_e2e_gold_corpus(CORPUS_PATH)
    report = evaluate_e2e_split(corpus, EndToEndGoldSplit.VALIDATION)

    assert report.passed is True
    assert report.metrics.total_cases == 2
    assert report.metrics.passed_cases == 2
    assert report.metrics.unsafe_fact_promotion_count == 0
    assert report.locked_evaluation_executed is False
