from __future__ import annotations

from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact
from renderer import MarkdownReasoningRenderer
from validation.performance_budget import PerformanceBudget, evaluate_performance_budget
from validation.performance_probe import measure_performance
from validation.renderer_quality import evaluate_reasoning_report


def _synthetic_final_report():  # type: ignore[no-untyped-def]
    fact = ReasoningArtifact(
        artifact_id="PERF-F1",
        statement="Synthetic performance fact.",
        status=KnowledgeStatus.FACT,
        evidence_refs=("PERF-E-1",),
    )
    conclusion = ReasoningArtifact(
        artifact_id="PERF-C1",
        statement="Synthetic performance conclusion.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("PERF-F1",),
    )
    result = ReasoningEngine((fact, conclusion)).evaluate("PERF-C1")
    return evaluate_reasoning_report(MarkdownReasoningRenderer(), result)


def test_final_report_e2e_is_actually_measured_against_declared_sla_budget() -> None:
    quality_report, measurement = measure_performance(
        "synthetic-final-report-e2e",
        _synthetic_final_report,
        model_calls=0,
        cost_units=0.0,
    )
    budget = PerformanceBudget(
        max_runtime_ms=2000.0,
        max_peak_memory_mb=64.0,
        max_model_calls=0,
        max_cost_units=0.0,
    )
    decision = evaluate_performance_budget(measurement, budget)

    assert quality_report.passed is True
    assert measurement.runtime_ms >= 0.0
    assert measurement.peak_memory_mb > 0.0
    assert measurement.model_calls == 0
    assert measurement.cost_units == 0.0
    assert decision.passed is True
    assert decision.violations == ()


def test_measurement_probe_rejects_invalid_declared_usage_counters() -> None:
    try:
        measure_performance("bad-model-calls", lambda: None, model_calls=-1, cost_units=0.0)
    except ValueError as exc:
        assert str(exc) == "model_calls must be non-negative"
    else:
        raise AssertionError("negative model_calls must fail closed")

    try:
        measure_performance("bad-cost", lambda: None, model_calls=0, cost_units=-0.1)
    except ValueError as exc:
        assert str(exc) == "cost_units must be non-negative"
    else:
        raise AssertionError("negative cost_units must fail closed")
