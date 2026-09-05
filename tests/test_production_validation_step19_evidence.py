from __future__ import annotations

import json
import tomllib
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence

ROOT = Path(".")
REPORT_PATH = Path("reports/production_validation/step_19.json")
POLICY_PATH = Path("docs/RELEASE_VERSIONING_MIGRATION_POLICY.md")
WORKFLOW_PATH = Path(".github/workflows/mvros-v1-release.yml")


def test_repository_step19_evidence_matches_current_release_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    report = json.loads((ROOT / REPORT_PATH).read_text(encoding="utf-8"))

    assert version == "1.0.1"
    assert report["project_version"] == version
    assert report["release_tag"] == f"v{version}"
    assert report["release_version_binding"]["project_version"] == version
    assert report["release_version_binding"]["expected_tag"] == f"v{version}"
    assert report["release_version_binding"]["existing_v1_0_0_must_not_move"] is True
    assert (ROOT / POLICY_PATH).is_file()
    assert (ROOT / WORKFLOW_PATH).is_file()

    decision = evaluate_generic_evidence(ROOT, 19)
    assert decision.passed is True
    assert decision.code == "PASS"
