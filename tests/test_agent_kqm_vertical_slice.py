from pathlib import Path

from agents.certification import AgentCertificationStatus, AgentCertificationThresholds
from agents.kqm import run_reference_agent_kqm

CORPUS_PATH = Path("data/quality/extraction_gold_v1.json")
TAXONOMY_PATH = Path("docs/quality/critical_facts_schema.yaml")


def policy() -> AgentCertificationThresholds:
    return AgentCertificationThresholds(
        min_precision=0.95,
        min_recall=0.90,
        min_f1=0.92,
        min_critical_recall=0.95,
    )


def test_reference_agent_kqm_vertical_slice_is_reproducible_and_locked_safe() -> None:
    result = run_reference_agent_kqm(CORPUS_PATH, TAXONOMY_PATH, policy())

    assert result.corpus_id == "extraction-gold-v1"
    assert result.corpus_status == "candidate_pending_independent_review"
    assert result.review_status == "not_reviewed"
    assert result.locked_split_executed is False

    assert result.development.true_positive == 18
    assert result.development.false_positive == 12
    assert result.development.false_negative == 42
    assert result.development.precision == 0.6
    assert result.development.recall == 0.3
    assert result.development.f1 == 0.4
    assert result.development.critical_fact_loss == 34
    assert result.development.provenance_completeness == 1.0

    assert result.validation.true_positive == 6
    assert result.validation.false_positive == 4
    assert result.validation.false_negative == 14
    assert result.validation.precision == 0.6
    assert result.validation.recall == 0.3
    assert result.validation.f1 == 0.4
    assert result.validation.critical_fact_loss == 11
    assert result.validation.provenance_completeness == 1.0

    assert result.certification.status is AgentCertificationStatus.REJECTED
    assert "recall below threshold" in result.certification.failures
    assert "critical_recall below threshold" in result.certification.failures
