from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")
EVIDENCE_DIR = Path("factory/production_validation_evidence")


def test_regenerated_dependent_certification_envelopes_are_active() -> None:
    for step in (16, 18):
        path = EVIDENCE_DIR / f"step_{step:02d}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["status"] == "PASS"
        assert payload["critical_gates_passed"] is True
        assert payload["certification_mode"] == "solo_maintainer"
        assert payload["independent_external_review"] == "NOT_PERFORMED"

        decision = evaluate_generic_evidence(ROOT, step)
        assert decision.passed is True
        assert decision.code == "PASS"
