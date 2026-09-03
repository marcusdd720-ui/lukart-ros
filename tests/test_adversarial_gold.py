from __future__ import annotations

from pathlib import Path

import pytest

from validation.adversarial_gold import (
    AdversarialGoldSplit,
    LockedAdversarialEvaluationError,
    evaluate_adversarial_split,
    load_adversarial_gold_corpus,
)

CORPUS_PATH = Path("data/quality/adversarial_gold_v1.json")


def test_adversarial_gold_has_sealed_locked_partition() -> None:
    corpus = load_adversarial_gold_corpus(CORPUS_PATH)

    assert corpus.corpus_id == "adversarial-gold-v1"
    assert len(corpus.cases_for_split(AdversarialGoldSplit.DEVELOPMENT)) == 4
    assert len(corpus.cases_for_split(AdversarialGoldSplit.VALIDATION)) == 2

    with pytest.raises(LockedAdversarialEvaluationError, match="locked adversarial evaluation"):
        corpus.cases_for_split(AdversarialGoldSplit.LOCKED_EVALUATION)


def test_development_adversarial_suite_preserves_all_vetoes() -> None:
    corpus = load_adversarial_gold_corpus(CORPUS_PATH)
    report = evaluate_adversarial_split(corpus, AdversarialGoldSplit.DEVELOPMENT)

    assert report.passed is True
    assert report.metrics.total_cases == 4
    assert report.metrics.passed_cases == 4
    assert report.metrics.evidence_veto_accuracy == 1.0
    assert report.metrics.required_abstention_accuracy == 1.0
    assert report.metrics.unresolved_challenge_accuracy == 1.0
    assert report.metrics.unsafe_fact_promotion_count == 0
    assert report.locked_evaluation_executed is False
    assert len(report.digest()) == 64


def test_validation_adversarial_suite_preserves_veto_and_unresolved_state() -> None:
    corpus = load_adversarial_gold_corpus(CORPUS_PATH)
    report = evaluate_adversarial_split(corpus, AdversarialGoldSplit.VALIDATION)

    assert report.passed is True
    assert report.metrics.total_cases == 2
    assert report.metrics.passed_cases == 2
    assert report.metrics.evidence_veto_accuracy == 1.0
    assert report.metrics.required_abstention_accuracy == 1.0
    assert report.metrics.unresolved_challenge_accuracy == 1.0
    assert report.metrics.unsafe_fact_promotion_count == 0
