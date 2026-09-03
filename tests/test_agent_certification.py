from __future__ import annotations

from agents.certification import (
    AgentCertificationStatus,
    AgentCertificationThresholds,
    AgentCertifier,
    contract_sha256,
)
from agents.reference_fact import ReferenceFactAgent
from validation.extraction_quality import ExtractionMetrics
from validation.independent_evaluation import ReviewOutcome


def metrics(**overrides: float | int) -> ExtractionMetrics:
    values: dict[str, float | int] = {
        "true_positive": 10,
        "false_positive": 0,
        "false_negative": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "critical_true_positive": 5,
        "critical_false_positive": 0,
        "critical_false_negative": 0,
        "critical_recall": 1.0,
        "critical_precision": 1.0,
        "critical_fact_loss": 0,
        "case_number_false_positive_rate": 0.0,
        "provenance_completeness": 1.0,
    }
    values.update(overrides)
    return ExtractionMetrics(**values)  # type: ignore[arg-type]


def thresholds() -> AgentCertificationThresholds:
    return AgentCertificationThresholds(
        min_precision=0.95,
        min_recall=0.90,
        min_f1=0.92,
        min_critical_recall=0.95,
    )


def test_contract_fingerprint_is_deterministic() -> None:
    contract = ReferenceFactAgent().contract
    assert contract_sha256(contract) == contract_sha256(contract)
    assert len(contract_sha256(contract)) == 64


def test_passing_metrics_wait_for_required_independent_review() -> None:
    report = AgentCertifier(thresholds()).evaluate(
        ReferenceFactAgent().contract,
        metrics(),
        corpus_version="gold-v1",
        split_name="validation",
    )

    assert report.status is AgentCertificationStatus.PENDING_EXTERNAL_REVIEW
    assert report.failures == ()


def test_metric_regression_rejects_agent() -> None:
    report = AgentCertifier(thresholds()).evaluate(
        ReferenceFactAgent().contract,
        metrics(critical_recall=0.80, critical_fact_loss=1),
        corpus_version="gold-v1",
        split_name="validation",
    )

    assert report.status is AgentCertificationStatus.REJECTED
    assert "critical_recall below threshold" in report.failures
    assert "critical_fact_loss above threshold" in report.failures


def test_independent_pass_can_certify_passing_agent() -> None:
    report = AgentCertifier(thresholds()).evaluate(
        ReferenceFactAgent().contract,
        metrics(),
        corpus_version="gold-v1",
        split_name="validation",
        external_review=ReviewOutcome.PASS,
    )

    assert report.status is AgentCertificationStatus.CERTIFIED
