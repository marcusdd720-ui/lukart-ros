from __future__ import annotations

from pathlib import Path

import pytest

from validation.reasoning_gold import (
    LockedReasoningEvaluationError,
    ReasoningGoldSplit,
    load_reasoning_gold_corpus,
)
from validation.reasoning_kqm import evaluate_reasoning_split


CORPUS_PATH = Path("data/quality/reasoning_gold_v1.json")


def test_reasoning_gold_corpus_has_protected_partition() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_PATH)

    assert corpus.corpus_id == "reasoning-gold-v1"
    assert len(corpus.cases_for_split(ReasoningGoldSplit.DEVELOPMENT)) == 4
    assert len(corpus.cases_for_split(ReasoningGoldSplit.VALIDATION)) == 2

    with pytest.raises(LockedReasoningEvaluationError, match="locked reasoning evaluation"):
        corpus.cases_for_split(ReasoningGoldSplit.LOCKED_EVALUATION)


def test_reasoning_kqm_development_contract_baseline() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_PATH)
    report = evaluate_reasoning_split(corpus, ReasoningGoldSplit.DEVELOPMENT)

    assert report.metrics.total_cases == 4
    assert report.metrics.decision_accuracy == 1.0
    assert report.metrics.valid_conclusion_recall == 1.0
    assert report.metrics.abstention_recall == 1.0
    assert report.metrics.unsafe_conclusion_rate == 0.0
    assert report.metrics.open_question_coverage == 1.0
    assert report.failures == ()
    assert report.locked_evaluation_executed is False


def test_reasoning_kqm_validation_contract_baseline() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_PATH)
    report = evaluate_reasoning_split(corpus, ReasoningGoldSplit.VALIDATION)

    assert report.metrics.total_cases == 2
    assert report.metrics.decision_accuracy == 1.0
    assert report.metrics.valid_conclusion_recall == 1.0
    assert report.metrics.abstention_recall == 1.0
    assert report.metrics.unsafe_conclusion_rate == 0.0
    assert report.metrics.open_question_coverage == 1.0
    assert report.failures == ()
    assert len(report.result_digests) == 2
