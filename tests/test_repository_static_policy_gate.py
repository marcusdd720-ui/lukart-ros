from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.repository_static_policy_gate import (
    validate_codeowners_coverage,
    validate_periodic_drift_schedule,
    validate_required_check_bindings,
    validate_required_check_matrix,
    validate_workflow_action_pins,
    validate_workflow_permissions,
)


def test_accepts_read_only_workflow_defaults() -> None:
    evidence = validate_workflow_permissions(
        ".github/workflows/ci.yml",
        {"permissions": {"contents": "read"}, "jobs": {"quality-gate": {"steps": []}}},
    )
    assert evidence["default_contents"] == "read"
    assert evidence["job_writes"] == []


def test_rejects_top_level_write_permission() -> None:
    workflow = {
        "permissions": {"contents": "read", "security-events": "write"},
        "jobs": {"codeql": {"steps": []}},
    }
    with pytest.raises(RuntimeError, match="top-level write"):
        validate_workflow_permissions(".github/workflows/codeql.yml", workflow)


def test_accepts_codeql_security_events_write_at_job_scope() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "codeql": {
                "permissions": {"contents": "read", "security-events": "write"},
                "steps": [
                    {
                        "uses": (
                            "github/codeql-action/analyze@"
                            "cdf488f595d80d6e07e03d4674febd5ab45fa938"
                        )
                    }
                ],
            }
        },
    }
    evidence = validate_workflow_permissions(".github/workflows/codeql.yml", workflow)
    assert evidence["job_writes"] == ["codeql:security-events"]


def test_rejects_job_write_without_same_job_consumer() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "unsafe": {
                "permissions": {"contents": "read", "id-token": "write"},
                "steps": [{"uses": "actions/checkout@" + "a" * 40}],
            }
        },
    }
    with pytest.raises(RuntimeError, match="same-job consumer"):
        validate_workflow_permissions(".github/workflows/unsafe.yml", workflow)


def test_accepts_attestation_oidc_writes_with_same_job_consumer() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "attest": {
                "permissions": {
                    "contents": "read",
                    "id-token": "write",
                    "attestations": "write",
                },
                "steps": [
                    {
                        "uses": "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
                    }
                ],
            }
        },
    }
    evidence = validate_workflow_permissions(".github/workflows/attest.yml", workflow)
    assert evidence["job_writes"] == ["attest:attestations", "attest:id-token"]


def test_accepts_contents_write_for_same_job_release_mutation() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "release-publish": {
                "permissions": {"actions": "read", "contents": "write"},
                "steps": [
                    {
                        "name": "Create release",
                        "run": 'gh release create "${TAG}" --target "${VALIDATED_SHA}" --draft',
                    }
                ],
            }
        },
    }
    evidence = validate_workflow_permissions(".github/workflows/release.yml", workflow)
    assert evidence["job_writes"] == ["release-publish:contents"]


def test_rejects_contents_write_without_release_mutation() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "unsafe": {
                "permissions": {"contents": "write"},
                "steps": [{"run": "echo no-release-mutation"}],
            }
        },
    }
    with pytest.raises(RuntimeError, match="same-job consumer"):
        validate_workflow_permissions(".github/workflows/unsafe.yml", workflow)


def test_accepts_pull_request_write_for_closure_preparation() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "prepare-closure-pr": {
                "permissions": {"contents": "read", "pull-requests": "write"},
                "steps": [
                    {
                        "run": (
                            "uv run --frozen --extra dev python "
                            "-m factory.closure_preparation --source-sha $SOURCE_SHA"
                        )
                    }
                ],
            }
        },
    }
    evidence = validate_workflow_permissions(".github/workflows/closure.yml", workflow)
    assert evidence["job_writes"] == ["prepare-closure-pr:pull-requests"]


def test_accepts_orchestrator_actions_and_contents_write_for_same_job_consumer() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "orchestrate-main": {
                "permissions": {"actions": "write", "contents": "write"},
                "steps": [
                    {
                        "run": (
                            "uv run --frozen --extra dev python -m "
                            "factory.stage_orchestrator --stage \"${STAGE_INPUT}\""
                        )
                    }
                ],
            }
        },
    }
    evidence = validate_workflow_permissions(".github/workflows/stage-orchestrator.yml", workflow)
    assert evidence["job_writes"] == [
        "orchestrate-main:actions",
        "orchestrate-main:contents",
    ]


def test_rejects_actions_write_without_orchestrator_invocation() -> None:
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {
            "unsafe": {
                "permissions": {"actions": "write", "contents": "read"},
                "steps": [{"run": "echo factory.stage_orchestrator"}],
            }
        },
    }
    with pytest.raises(RuntimeError, match="same-job consumer"):
        validate_workflow_permissions(".github/workflows/unsafe.yml", workflow)


def _write_workflow(root: Path, content: str) -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "test.yml").write_text(content, encoding="utf-8")


def test_accepts_full_sha_pinned_external_actions(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "steps:\n  - uses: actions/checkout@" + "a" * 40 + "\n",
    )
    evidence = validate_workflow_action_pins(tmp_path)
    assert evidence["scanned_files"] == 1
    assert evidence["external_action_references"] == 1
    assert evidence["findings"] == []


def test_rejects_mutable_external_action_ref(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "steps:\n  - uses: actions/checkout@v4\n")
    with pytest.raises(RuntimeError, match="workflow action pin drift"):
        validate_workflow_action_pins(tmp_path)


def test_codeowners_wildcard_covers_canonical_critical_surface() -> None:
    evidence = validate_codeowners_coverage(
        ["core/case_ledger.py", "config/**", ".github/workflows/**"],
        "* @owner\n",
    )
    assert evidence["critical_paths"] == 3


def test_codeowners_rejects_uncovered_critical_surface() -> None:
    with pytest.raises(RuntimeError, match="unowned"):
        validate_codeowners_coverage(["config/**"], "/core/** @owner\n")


def test_canonical_policy_self_protects_governance_enforcers() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / "config" / "enterprise_v1.json").read_text(encoding="utf-8"))
    critical_paths = set(policy["h2_repository_policy"]["review_integrity"]["critical_paths"])
    required = {
        "scripts/repository_governance_integrity_gate.py",
        "scripts/repository_static_policy_gate.py",
        "tests/test_repository_governance_integrity_gate.py",
        "tests/test_repository_static_policy_gate.py",
    }
    assert required <= critical_paths


def _policy(contexts: list[str]) -> dict[str, object]:
    return {
        "h2_repository_policy": {
            "required_checks": [
                {
                    "context": context,
                    "integration_id": 15368,
                    "workflow": ".github/workflows/ci.yml",
                    "job_id": "quality-gate",
                }
                for context in contexts
            ]
        }
    }


def _ci(versions: list[str]) -> dict[str, object]:
    return {
        "jobs": {
            "quality-gate": {
                "strategy": {"matrix": {"python-version": versions}},
            }
        }
    }


def _binding_policy(checks: list[dict[str, object]]) -> dict[str, object]:
    return {"h2_repository_policy": {"required_checks": checks}}


def _binding(
    *,
    context: str = "gate",
    workflow: str = ".github/workflows/test.yml",
    job_id: str = "gate",
) -> dict[str, object]:
    return {
        "context": context,
        "integration_id": 15368,
        "workflow": workflow,
        "job_id": job_id,
    }


def test_required_check_binding_accepts_existing_workflow_and_job(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "jobs:\n  gate:\n    steps: []\n")
    evidence = validate_required_check_bindings(
        _binding_policy([_binding()]),
        root=tmp_path,
    )
    assert evidence["count"] == 1


def test_required_check_binding_rejects_missing_job(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "jobs:\n  other:\n    steps: []\n")
    with pytest.raises(RuntimeError, match="job 'gate' missing"):
        validate_required_check_bindings(
            _binding_policy([_binding()]),
            root=tmp_path,
        )


def test_required_check_binding_rejects_duplicate_context(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "jobs:\n  gate:\n    steps: []\n")
    with pytest.raises(RuntimeError, match="duplicate context"):
        validate_required_check_bindings(
            _binding_policy([_binding(), _binding()]),
            root=tmp_path,
        )


def test_required_check_binding_rejects_workflow_path_escape(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="escapes policy surface"):
        validate_required_check_bindings(
            _binding_policy([_binding(workflow="../unsafe.yml")]),
            root=tmp_path,
        )


def test_required_check_matrix_matches_ci_matrix() -> None:
    evidence = validate_required_check_matrix(
        _policy(["quality-gate (3.11)", "quality-gate (3.12)"]),
        _ci(["3.11", "3.12"]),
    )
    assert evidence["python_versions"] == ["3.11", "3.12"]


def test_required_check_matrix_rejects_missing_context() -> None:
    with pytest.raises(RuntimeError, match="matrix drift"):
        validate_required_check_matrix(
            _policy(["quality-gate (3.11)"]),
            _ci(["3.11", "3.12"]),
        )


def test_accepts_periodic_drift_monitor_schedule() -> None:
    evidence = validate_periodic_drift_schedule(
        'on:\n  schedule:\n    - cron: "17 4 * * *"\n  workflow_dispatch:\n'
    )
    assert evidence["cron"] == "17 4 * * *"


def test_rejects_missing_periodic_drift_monitor_schedule() -> None:
    with pytest.raises(RuntimeError, match="scheduled trigger"):
        validate_periodic_drift_schedule("on:\n  workflow_dispatch:\n")
