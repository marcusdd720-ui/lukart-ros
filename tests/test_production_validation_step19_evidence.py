from __future__ import annotations

import json
import tomllib
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")
REPORT_PATH = Path("reports/production_validation/step_19.json")
POLICY_PATH = Path("docs/RELEASE_VERSIONING_MIGRATION_POLICY.md")
WORKFLOW_PATH = Path(".github/workflows/mvros-v1-release.yml")


def test_repository_step19_evidence_matches_immutable_release_baseline() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    enterprise = project["tool"]["lukart"]["enterprise"]
    baseline_version = enterprise["immutable_baseline_version"]
    report = json.loads((ROOT / REPORT_PATH).read_text(encoding="utf-8"))

    assert baseline_version == "1.0.1"
    assert report["project_version"] == baseline_version
    assert report["release_tag"] == f"v{baseline_version}"
    assert report["release_version_binding"]["project_version"] == baseline_version
    assert report["release_version_binding"]["expected_tag"] == f"v{baseline_version}"
    assert report["release_version_binding"]["existing_v1_0_0_must_not_move"] is True
    assert enterprise["release_enabled"] is False
    assert (ROOT / POLICY_PATH).is_file()
    assert (ROOT / WORKFLOW_PATH).is_file()

    decision = evaluate_generic_evidence(ROOT, 19)
    assert decision.passed is True
    assert decision.code == "PASS"
