from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence


def test_repository_step7_evidence_is_bound_and_valid() -> None:
    decision = evaluate_generic_evidence(Path("."), 7)

    assert decision.passed is True
    assert decision.code == "PASS"
