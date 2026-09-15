from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CHECKOUT_SHA = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_SHA = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD_SHA = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "name",
    ["case-testy-pr-gate.yml", "case-testy-post-merge.yml", "case-testy-forensic.yml"],
)
def test_case_testy_workflows_pin_actions_and_frozen_uv(name: str) -> None:
    text = _text(name)
    assert CHECKOUT_SHA in text
    assert SETUP_SHA in text
    assert UPLOAD_SHA in text
    assert 'uv==0.12.10' in text
    assert "uv sync --frozen --extra dev" in text
    assert "if-no-files-found: error" in text


def test_pr_gate_has_stable_check_and_runs_all_required_profiles() -> None:
    text = _text("case-testy-pr-gate.yml")
    assert "name: case-testy-pr-gate" in text
    assert "github.event.pull_request.head.sha" in text
    assert "test_profiles FAST" in text
    assert "test_profiles PR" in text
    assert "test_profiles FULL" in text
    assert "Validate required reports" in text


def test_post_merge_is_bound_to_github_sha() -> None:
    text = _text("case-testy-post-merge.yml")
    assert "branches: [main]" in text
    assert "HEAD_SHA: ${{ github.sha }}" in text
    assert "ref: ${{ github.sha }}" in text
    assert "test_profiles POST-MERGE" in text
    assert "post-merge.json --profile POST-MERGE" in text


def test_forensic_is_scheduled_and_manually_dispatchable() -> None:
    text = _text("case-testy-forensic.yml")
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "17 2 * * *"' in text
    assert "test_profiles FORENSIC" in text
    assert "forensic.json --profile FORENSIC" in text
