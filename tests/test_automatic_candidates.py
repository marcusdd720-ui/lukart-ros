from __future__ import annotations

import pytest

from learning.automatic_candidates import (
    AutomaticCandidateGenerator,
    CandidateGenerationRule,
    CandidateGenerationStatus,
)
from learning.models import ChangeKind, LearningSource, MeasuredFailure


def _failure(code: str = "DECISION_MISMATCH") -> MeasuredFailure:
    return MeasuredFailure(
        failure_id="MF-AUTO-1",
        source=LearningSource.REASONING_KQM,
        corpus_id="reasoning-gold-v2",
        corpus_version="2.0.0",
        split="development",
        evaluator_version="reasoning-kqm-v1",
        source_sha="a" * 40,
        case_id="SYN-R-201",
        code=code,
        expected="conclude",
        actual="abstain",
        result_digest="b" * 64,
        report_digest="c" * 64,
    )


def _rule() -> CandidateGenerationRule:
    return CandidateGenerationRule(
        rule_id="AUTO-R-001",
        source=LearningSource.REASONING_KQM,
        failure_code="DECISION_MISMATCH",
        target_component="reasoning.engine",
        change_kind=ChangeKind.RULE,
        hypothesis="Evaluate whether a bounded rule change resolves the measured mismatch.",
        success_criteria=(
            "decision_accuracy must improve on development and validation",
            "unsafe_conclusion_rate must not regress",
        ),
    )


def test_generator_creates_only_learning_candidate_from_exact_curated_rule() -> None:
    decision = AutomaticCandidateGenerator((_rule(),)).generate(_failure())

    assert decision.status is CandidateGenerationStatus.GENERATED
    assert decision.rule_id == "AUTO-R-001"
    assert decision.candidate is not None
    assert decision.candidate.target_component == "reasoning.engine"
    assert decision.candidate.change_kind is ChangeKind.RULE
    assert decision.candidate.source_failure_digest == _failure().digest()


def test_generator_abstains_on_unknown_failure_instead_of_guessing() -> None:
    decision = AutomaticCandidateGenerator((_rule(),)).generate(_failure("UNKNOWN_FAILURE"))

    assert decision.status is CandidateGenerationStatus.ABSTAINED
    assert decision.candidate is None
    assert decision.rule_id is None


def test_generator_rejects_ambiguous_rule_table_at_construction() -> None:
    duplicate = CandidateGenerationRule(
        rule_id="AUTO-R-002",
        source=LearningSource.REASONING_KQM,
        failure_code="DECISION_MISMATCH",
        target_component="reasoning.validation",
        change_kind=ChangeKind.RULE,
        hypothesis="A second mapping would make automatic generation ambiguous.",
        success_criteria=("must improve",),
    )

    with pytest.raises(ValueError, match="unique by source and failure code"):
        AutomaticCandidateGenerator((_rule(), duplicate))


def test_generated_candidate_has_no_patch_or_deployment_authority_fields() -> None:
    decision = AutomaticCandidateGenerator((_rule(),)).generate(_failure())
    candidate = decision.candidate

    assert candidate is not None
    assert not hasattr(candidate, "patch")
    assert not hasattr(candidate, "merge")
    assert not hasattr(candidate, "deploy")
    assert not hasattr(candidate, "production_write")
