from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.github_actions_runtime_gate import audit_workflow_action_runtime

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"


def _write_policy(root: Path, *, runtime: str = "node24") -> None:
    path = root / "config/github_actions_runtime_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "lukart.github-actions-runtime-policy.v1",
                "minimum_node_runtime": 24,
                "verification_state": "ENGINEERING_VERIFIED",
                "verified_at": "2026-09-06",
                "approved_actions": {
                    "actions/checkout": {
                        "sha": CHECKOUT_SHA,
                        "version": "v6",
                        "runtime": runtime,
                    }
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_workflow(root: Path, reference: str) -> None:
    path = root / ".github/workflows/test.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: test\n"
        "on: [push]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: {reference}\n",
        encoding="utf-8",
    )


def test_repository_actions_are_runtime_verified() -> None:
    report = audit_workflow_action_runtime(ROOT)
    assert report.passed
    assert report.scanned_files > 0
    assert report.external_action_references > 0


def test_unknown_external_action_fails_closed(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_workflow(tmp_path, f"example/unknown@{'a' * 40}")

    report = audit_workflow_action_runtime(tmp_path)

    assert not report.passed
    assert "not runtime-verified" in report.findings[0].reason


def test_changed_action_sha_requires_explicit_rebinding(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_workflow(tmp_path, f"actions/checkout@{'1' * 40}")

    report = audit_workflow_action_runtime(tmp_path)

    assert not report.passed
    assert "verified Node24 binding" in report.findings[0].reason


def test_movable_action_ref_fails_closed(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_workflow(tmp_path, "actions/checkout@v6")

    report = audit_workflow_action_runtime(tmp_path)

    assert not report.passed
    assert "not a full SHA" in report.findings[0].reason


def test_node20_policy_binding_is_rejected(tmp_path: Path) -> None:
    _write_policy(tmp_path, runtime="node20")
    _write_workflow(tmp_path, f"actions/checkout@{CHECKOUT_SHA}")

    with pytest.raises(RuntimeError, match="must be verified as node24"):
        audit_workflow_action_runtime(tmp_path)
