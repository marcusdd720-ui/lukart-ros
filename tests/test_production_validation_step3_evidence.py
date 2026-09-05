from __future__ import annotations

import json
from pathlib import Path

from agents.certification import AgentCertificationThresholds
from agents.kqm import run_reference_agent_kqm
from factory.production_validation_orchestrator import (
    EXTRACTION_CORPUS,
    EXTRACTION_FREEZE,
    EXTRACTION_REVIEW,
    evaluate_extraction_review,
    evaluate_generic_evidence,
    sha256_file,
)
from validation.extraction_quality import ExtractionMetrics

ROOT = Path(".")
REPORT_PATH = Path("reports/production_validation/step_03.json")
TAXONOMY_PATH = Path("docs/quality/critical_facts_schema.yaml")


def _metric_dict(metrics: ExtractionMetrics) -> dict[str, float | int]:
    return {
        "true_positive": metrics.true_positive,
        "false_positive": metrics.false_positive,
        "false_negative": metrics.false_negative,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "critical_true_positive": metrics.critical_true_positive,
        "critical_false_positive": metrics.critical_false_positive,
        "critical_false_negative": metrics.critical_false_negative,
        "critical_recall": metrics.critical_recall,
        "critical_precision": metrics.critical_precision,
        "critical_fact_loss": metrics.critical_fact_loss,
        "case_number_false_positive_rate": metrics.case_number_false_positive_rate,
        "provenance_completeness": metrics.provenance_completeness,
    }


def test_repository_step3_evidence_is_bound_measured_and_locked_safe() -> None:
    review_decision = evaluate_extraction_review(ROOT)
    assert review_decision.passed is True

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    review = json.loads((ROOT / EXTRACTION_REVIEW).read_text(encoding="utf-8"))
    freeze = json.loads((ROOT / EXTRACTION_FREEZE).read_text(encoding="utf-8"))

    corpus_sha256 = sha256_file(ROOT / EXTRACTION_CORPUS)
    assert freeze["status"] == "FROZEN"
    assert freeze["corpus_sha256"] == corpus_sha256
    assert report["frozen_corpus"]["corpus_sha256"] == corpus_sha256
    assert report["frozen_corpus"]["reviewed_sha"] == review["reviewed_sha"]
    assert review["reviewer_kind"] == "human"
    assert review["decision"] == "APPROVED"

    thresholds = report["thresholds"]
    policy = AgentCertificationThresholds(
        min_precision=thresholds["min_precision"],
        min_recall=thresholds["min_recall"],
        min_f1=thresholds["min_f1"],
        min_critical_recall=thresholds["min_critical_recall"],
        min_provenance_completeness=thresholds["min_provenance_completeness"],
        max_critical_fact_loss=thresholds["max_critical_fact_loss"],
        max_case_number_false_positive_rate=thresholds[
            "max_case_number_false_positive_rate"
        ],
    )
    result = run_reference_agent_kqm(ROOT / EXTRACTION_CORPUS, TAXONOMY_PATH, policy)

    assert result.locked_split_executed is False
    assert result.certification.failures == ()
    assert _metric_dict(result.development) == report["development"]
    assert _metric_dict(result.validation) == report["validation"]
    assert all(report["threshold_evaluation"].values())
    assert report["certification_decision"] == "PASS"

    step_decision = evaluate_generic_evidence(ROOT, 3)
    assert step_decision.passed is True
    assert step_decision.code == "PASS"
