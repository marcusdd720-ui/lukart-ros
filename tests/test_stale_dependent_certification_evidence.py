from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")
EVIDENCE_DIR = Path("factory/production_validation_evidence")


def test_remaining_dependent_certification_envelopes_are_quarantined() -> None:
    for step in (6, 8, 16, 18):
        path = EVIDENCE_DIR / f"step_{step:02d}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["status"] == "STALE"
        assert payload["critical_gates_passed"] is False
        assert isinstance(payload["stale_reason"], str)
        assert payload["stale_reason"].strip()

        decision = evaluate_generic_evidence(ROOT, step)
        assert decision.passed is False
        assert decision.code == "STEP_EVIDENCE_INVALID"
