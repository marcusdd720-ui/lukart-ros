from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence
from validation.agent_certification_bundle import build_reference_fact_agent_bundle

ROOT = Path(".")
REPORT_PATH = Path("reports/production_validation/step_08.json")
EVIDENCE_PATH = Path("factory/production_validation_evidence/step_08.json")


def test_repository_step8_is_fresh_solo_agent_certification() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    validated_sha = str(report["validated_sha"])

    generated = build_reference_fact_agent_bundle(ROOT, validated_sha=validated_sha)

    assert generated == report
    assert report["certification_mode"] == "solo_maintainer"
    assert report["independent_external_review"] == "NOT_PERFORMED"
    certification = report["certification_reports"][0]
    assert certification["external_review"] == "NOT_PERFORMED"
    assert certification["independent_review_required"] is False
    assert certification["status"] == "certified"
    assert report["locked_evaluation_used_for_tuning"] is False
    assert evidence["artifact_path"] == REPORT_PATH.as_posix()
    assert evidence["artifact_sha256"]

    decision = evaluate_generic_evidence(ROOT, 8)
    assert decision.passed is True
    assert decision.code == "PASS"
