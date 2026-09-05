from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.reasoning_certification import (
    ReasoningCertificationError,
    certification_readiness,
    load_certification_policy,
    measure_contradiction_handling,
    sha256_file,
)
from validation.reasoning_gold import load_reasoning_gold_corpus


CORPUS_PATH = Path("data/quality/reasoning_gold_v2.json")
REVIEW_PATH = Path("docs/quality/reviews/reasoning_gold_v2_review.json")
FREEZE_PATH = Path("data/quality/reasoning_gold_v2.freeze.json")
POLICY_PATH = Path("docs/quality/reasoning_certification_policy_v1.json")


def test_step6_policy_is_bound_before_locked_execution() -> None:
    policy = load_certification_policy(POLICY_PATH)

    assert policy.corpus_id == "reasoning-gold-v2"
    assert policy.corpus_sha256 == sha256_file(CORPUS_PATH)
    assert policy.locked_use == "certification_only"
    assert policy.locked_evaluation_authorized is True
    assert policy.thresholds.decision_accuracy_min == 1.0
    assert policy.thresholds.abstention_recall_min == 1.0
    assert policy.thresholds.unsafe_conclusion_rate_max == 0.0


def test_step6_readiness_does_not_execute_locked_split() -> None:
    readiness = certification_readiness(
        corpus_path=CORPUS_PATH,
        review_path=REVIEW_PATH,
        freeze_path=FREEZE_PATH,
        policy_path=POLICY_PATH,
    )

    assert readiness["ready"] is True
    assert readiness["locked_evaluation_executed"] is False
    assert readiness["contradiction_pass_rate"] == 1.0


def test_step6_contradiction_measurement_uses_non_locked_case() -> None:
    corpus = load_reasoning_gold_corpus(CORPUS_PATH)
    policy = load_certification_policy(POLICY_PATH)

    measurements = measure_contradiction_handling(corpus, policy)

    assert len(measurements) == 1
    measurement = measurements[0]
    assert measurement.case_id == "SYN-R-211"
    assert measurement.contradiction_detected is True
    assert measurement.expected_outcome == "ABSTAIN"
    assert measurement.actual_outcome == "ABSTAIN"
    assert measurement.passed is True


def test_step6_policy_requires_explicit_locked_authorization(tmp_path: Path) -> None:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["locked_evaluation_authorized"] = False
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ReasoningCertificationError,
        match="locked evaluation is not explicitly authorized",
    ):
        load_certification_policy(path)
