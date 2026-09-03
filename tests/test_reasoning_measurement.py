from __future__ import annotations

from pathlib import Path

from validation.measurement import MeasurementCollector
from validation.reasoning_gold import ReasoningGoldSplit, load_reasoning_gold_corpus
from validation.reasoning_kqm import evaluate_reasoning_split


def test_reasoning_metrics_use_existing_measurement_snapshot_contract() -> None:
    corpus = load_reasoning_gold_corpus(Path("data/quality/reasoning_gold_v1.json"))
    report = evaluate_reasoning_split(corpus, ReasoningGoldSplit.VALIDATION)
    snapshot = MeasurementCollector().from_reasoning(report.metrics)

    metrics = snapshot.as_dict()["metrics"]
    assert metrics["decision_accuracy"] == 1.0
    assert metrics["unsafe_conclusion_rate"] == 0.0
    assert metrics["open_question_coverage"] == 1.0
