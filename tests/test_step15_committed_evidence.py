from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence


def test_committed_step15_private_pilot_evidence_passes() -> None:
    root = Path(__file__).resolve().parents[1]

    decision = evaluate_generic_evidence(root, 15)

    assert decision.passed is True
    assert decision.code == "PASS"
