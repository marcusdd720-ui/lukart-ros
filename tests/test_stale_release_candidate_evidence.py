from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_release_candidate

ROOT = Path(".")
EVIDENCE = Path("factory/production_validation_evidence/step_20.json")
REPORT = Path("reports/production_validation/step_20.json")
MANIFEST = Path("reports/production_validation/lukart_v1_release_manifest.json")


def test_repository_step20_is_current_v101_release_candidate_evidence() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert evidence["status"] == "PASS"
    assert evidence["critical_gates_passed"] is True
    assert evidence["certification_mode"] == "solo_maintainer"
    assert evidence["independent_external_review"] == "NOT_PERFORMED"
    assert "stale_reason" not in evidence
    assert "replacement_required_after_steps_1_19_pass" not in evidence

    assert report["decision"] == "RELEASE_CANDIDATE_PASS"
    assert report["release_manifest"]["product_version"] == "1.0.1"
    assert report["steps_1_19_digest"] == manifest["steps_1_19_digest"]
    assert manifest["product_version"] == "1.0.1"
    assert manifest["independent_external_review"] == "NOT_PERFORMED"

    decision = evaluate_release_candidate(ROOT)
    assert decision.passed is True
    assert decision.code == "PASS"
