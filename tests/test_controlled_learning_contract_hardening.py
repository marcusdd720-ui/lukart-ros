from __future__ import annotations

import pytest

from learning import (
    ExperimentContract,
    FailureCorpus,
    MetricDirection,
    MetricGuardrail,
)


def test_failure_corpus_rejects_malformed_report_digest() -> None:
    with pytest.raises(ValueError, match="source report digest must be SHA-256"):
        FailureCorpus(
            corpus_id="failure-reasoning-gold-v1-development",
            version="1.0.0",
            source_report_digest="not-a-digest",
            failures=(),
        )


def test_experiment_contract_rejects_malformed_candidate_digest() -> None:
    with pytest.raises(ValueError, match="candidate_digest must be a SHA-256 digest"):
        ExperimentContract(
            experiment_id="EXP-P4-DIGEST",
            candidate_digest="not-a-digest",
            target_component="reasoning.engine",
            baseline_revision="baseline-a",
            candidate_revision="candidate-b",
            sandbox_id="sandbox-p4",
            allowed_splits=("development",),
            guardrails=(
                MetricGuardrail(
                    "decision_accuracy",
                    MetricDirection.HIGHER_IS_BETTER,
                ),
            ),
        )
