from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.production_validation_orchestrator import (
    evaluate_release_candidate,
    production_validation_chain_digest,
)

ROOT = Path(".")
EXPECTED_CHAIN_DIGEST = "64f575201a3f693024795bc99920e5d817fe099e942cebeb6c15da142481fc7a"


def test_step20_v101_release_candidate_matches_live_steps_1_19_chain() -> None:
    manifest_path = ROOT / "reports/production_validation/lukart_v1_release_manifest.json"
    report_path = ROOT / "reports/production_validation/step_20.json"
    evidence_path = ROOT / "factory/production_validation_evidence/step_20.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    chain_digest, chain_decision = production_validation_chain_digest(ROOT)
    assert chain_decision is None
    assert chain_digest == EXPECTED_CHAIN_DIGEST

    assert manifest["product_version"] == "1.0.1"
    assert manifest["steps_1_19_digest"] == chain_digest
    assert manifest["certification_mode"] == "solo_maintainer"
    assert manifest["independent_external_review"] == "NOT_PERFORMED"

    assert report["steps_1_19_digest"] == chain_digest
    assert report["release_workflow_authorization"] == "PENDING_POST_MERGE_SAME_SHA_GATES"
    assert report["release_manifest"]["sha256"] == hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()

    assert evidence["status"] == "PASS"
    assert evidence["artifact_sha256"] == hashlib.sha256(report_path.read_bytes()).hexdigest()

    decision = evaluate_release_candidate(ROOT)
    assert decision.passed is True
    assert decision.code == "PASS"
