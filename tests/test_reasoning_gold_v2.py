from __future__ import annotations

from pathlib import Path

import pytest

from validation.reasoning_gold import (
    LockedReasoningEvaluationError,
    ReasoningGoldSplit,
    load_reasoning_gold_corpus,
)
from validation.reasoning_kqm import evaluate_reasoning_split

CORPUS_V2_PATH = Path("data/quality/reasoning_gold_v2.json")


def test_reasoning_gold_v2_has_broader_protected_partition() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_V2_PATH)

    assert corpus.corpus_id == "reasoning-gold-v2"
    assert corpus.version == "2.0.0"
    assert corpus.status == "candidate_pending_independent_review"
    assert corpus.review_status == "not_reviewed"
    assert len(corpus.cases_for_split(ReasoningGoldSplit.DEVELOPMENT)) == 8
    assert len(corpus.cases_for_split(ReasoningGoldSplit.VALIDATION)) == 4

    with pytest.raises(LockedReasoningEvaluationError, match="locked reasoning evaluation"):
        corpus.cases_for_split(ReasoningGoldSplit.LOCKED_EVALUATION)


def test_reasoning_gold_v2_development_baseline_is_measurable() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_V2_PATH)
    report = evaluate_reasoning_split(corpus, ReasoningGoldSplit.DEVELOPMENT)

    assert report.metrics.total_cases == 8
    assert report.metrics.decision_accuracy == 1.0
    assert report.metrics.valid_conclusion_recall == 1.0
    assert report.metrics.abstention_recall == 1.0
    assert report.metrics.unsafe_conclusion_rate == 0.0
    assert report.metrics.open_question_coverage == 1.0
    assert report.failures == ()
    assert report.locked_evaluation_executed is False


def test_reasoning_gold_v2_validation_baseline_is_measurable() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_V2_PATH)
    report = evaluate_reasoning_split(corpus, ReasoningGoldSplit.VALIDATION)

    assert report.metrics.total_cases == 4
    assert report.metrics.decision_accuracy == 1.0
    assert report.metrics.valid_conclusion_recall == 1.0
    assert report.metrics.abstention_recall == 1.0
    assert report.metrics.unsafe_conclusion_rate == 0.0
    assert report.metrics.open_question_coverage == 1.0
    assert report.failures == ()
    assert report.locked_evaluation_executed is False


def test_reasoning_gold_v1_contract_still_loads() -> None:
    corpus = load_reasoning_gold_corpus(Path("data/quality/reasoning_gold_v1.json"))

    assert corpus.version == "1.0.0"
    assert len(corpus.cases_for_split(ReasoningGoldSplit.DEVELOPMENT)) == 4
    assert len(corpus.cases_for_split(ReasoningGoldSplit.VALIDATION)) == 2
