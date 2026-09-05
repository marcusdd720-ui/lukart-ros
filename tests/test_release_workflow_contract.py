from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_production_validation_workflow_fails_closed_when_program_is_incomplete() -> None:
    workflow = workflow_text("production-validation-program.yml")

    assert "name: Enforce complete program state" in workflow
    assert 'status != "COMPLETE"' in workflow
    assert "last_completed != 20" in workflow
    assert "PRODUCTION_VALIDATION_RELEASE_GATE=PASS" in workflow
    assert "raise SystemExit(1)" in workflow


def test_release_workflow_requires_companion_gates_on_same_sha() -> None:
    workflow = workflow_text("mvros-v1-release.yml")

    assert "actions: read" in workflow
    assert "Require all release validation workflows on the same SHA" in workflow
    for required_workflow in (
        "CI Foundation",
        "Architectural Audit 1.0",
        "Stage Gate",
        "Stage Orchestrator",
        "Production Validation Program",
    ):
        assert required_workflow in workflow
    assert 'run.get("head_sha") == validated_sha' in workflow
    assert "RELEASE_COMPANION_WORKFLOWS=PASS" in workflow


def test_release_workflow_never_moves_an_existing_version_tag() -> None:
    workflow = workflow_text("mvros-v1-release.yml")

    assert "ALLOW_STALE_V1_RECONCILIATION" not in workflow
    assert "gh release delete" not in workflow
    assert 'git push origin ":refs/tags/$TAG"' not in workflow
    assert "Refusing to move an existing release tag" in workflow
    assert "Bump the project version for a new release" in workflow
