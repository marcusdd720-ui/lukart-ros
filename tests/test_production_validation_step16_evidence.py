from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")


def test_step16_solo_maintainer_evidence_is_truthful_and_valid() -> None:
    evidence = json.loads(
        (ROOT / "factory/production_validation_evidence/step_16.json").read_text(
            encoding="utf-8"
        )
    )
    report = json.loads(
        (ROOT / "reports/production_validation/step_16.json").read_text(encoding="utf-8")
    )
    review = json.loads(
        (ROOT / "docs/quality/reviews/step_16_independent_review.json").read_text(
            encoding="utf-8"
        )
    )

    assert evidence["status"] == "PASS"
    assert evidence["certification_mode"] == "solo_maintainer"
    assert evidence["independent_external_review"] == "NOT_PERFORMED"
    assert report["certification_mode"] == "solo_maintainer"
    assert report["independent_external_review"] == "NOT_PERFORMED"
    assert review["reviewer_kind"] == "maintainer"
    assert review["reviewer_independent"] is False
    assert review["independent_external_review"] == "NOT_PERFORMED"

    decision = evaluate_generic_evidence(ROOT, 16)
    assert decision.passed is True
    assert decision.code == "PASS"
