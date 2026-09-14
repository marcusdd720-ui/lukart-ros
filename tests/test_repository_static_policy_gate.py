from __future__ import annotations

import pytest

from scripts.repository_static_policy_gate import (
    validate_codeowners_coverage,
    validate_periodic_drift_schedule,
    validate_required_check_matrix,
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


def test_codeowners_wildcard_covers_canonical_critical_surface() -> None:
    evidence = validate_codeowners_coverage(
        ["core/case_ledger.py", "config/**", ".github/workflows/**"],
        "* @owner\n",
    )
    assert evidence["critical_paths"] == 3


def test_codeowners_rejects_uncovered_critical_surface() -> None:
    with pytest.raises(RuntimeError, match="unowned"):
        validate_codeowners_coverage(["config/**"], "/core/** @owner\n")


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
