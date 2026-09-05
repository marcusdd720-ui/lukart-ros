from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")
EVIDENCE = Path("factory/production_validation_evidence/step_20.json")
REPORT = Path("reports/production_validation/step_20.json")


def test_repository_step20_is_historical_not_current_release_evidence() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert evidence["status"] == "STALE"
    assert evidence["critical_gates_passed"] is False
    assert evidence["replacement_required_after_steps_1_19_pass"] is True
    assert report["release_manifest"]["product_version"] == "1.0.0"

    decision = evaluate_generic_evidence(ROOT, 20)
    assert decision.passed is False
    assert decision.code == "STEP_EVIDENCE_INVALID"
