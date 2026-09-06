from __future__ import annotations

import pytest

from scripts.hardcore_h2_policy import validate_snapshot

CANDIDATE = "a" * 40
INTEGRATION_ID = 15368
RULESET_ID = 22352216


def _bindings() -> list[dict[str, object]]:
    return [
        {
            "context": "quality-gate (3.11)",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/ci.yml",
            "job_id": "quality-gate",
        },
        {
            "context": "quality-gate (3.12)",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/ci.yml",
            "job_id": "quality-gate",
        },
        {
            "context": "quality-gate (3.13)",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/ci.yml",
            "job_id": "quality-gate",
        },
        {
            "context": "gate",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/stage-gate.yml",
            "job_id": "gate",
        },
        {
            "context": "orchestrate",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/stage-orchestrator.yml",
            "job_id": "orchestrate",
        },
        {
            "context": "audit",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/architectural-audit.yml",
            "job_id": "audit",
        },
        {
            "context": "smoke-test",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/github-app-smoke.yml",
            "job_id": "smoke-test",
        },
        {
            "context": "program-gate",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/production-validation-program.yml",
            "job_id": "program-gate",
        },
        {
            "context": "enterprise-gate",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/enterprise-hardening.yml",
            "job_id": "enterprise-gate",
        },
        {
            "context": "codeql",
            "integration_id": INTEGRATION_ID,
            "workflow": ".github/workflows/codeql-enterprise.yml",
            "job_id": "codeql",
        },
    ]


def _policy() -> dict[str, object]:
    return {
        "h2_repository_policy": {
            "repository": "marcusdd720-ui/lukart-ros",
            "ruleset_name": "LUKART main protection",
            "target": "branch",
            "enforcement": "active",
            "default_branch_condition": "~DEFAULT_BRANCH",
            "required_rule_types": [
                "deletion",
                "non_fast_forward",
                "pull_request",
                "required_status_checks",
            ],
            "strict_required_status_checks": True,
            "do_not_enforce_on_create": False,
            "allowed_bypass_actors": [],
            "current_user_can_bypass": "never",
            "required_checks": _bindings(),
        }
    }


def _rulesets() -> list[object]:
    return [
        {
            "id": RULESET_ID,
            "name": "LUKART main protection",
            "target": "branch",
            "enforcement": "active",
        },
        {
            "id": 2,
            "name": "LUKART v1.0.1 immutable tag",
            "target": "tag",
            "enforcement": "active",
        },
    ]


def _detail() -> dict[str, object]:
    checks = [
        {
            "context": str(binding["context"]),
            "integration_id": INTEGRATION_ID,
        }
        for binding in _bindings()
    ]
    return {
        "id": RULESET_ID,
        "name": "LUKART main protection",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "exclude": [],
                "include": ["~DEFAULT_BRANCH"],
            }
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {}},
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": checks,
                },
            },
        ],
        "bypass_actors": [],
        "current_user_can_bypass": "never",
    }


def _workflows() -> dict[str, str]:
    workflows: dict[str, str] = {}
    for binding in _bindings():
        path = str(binding["workflow"])
        job_id = str(binding["job_id"])
        existing = workflows.get(path, "on:\n  pull_request:\njobs:\n")
        marker = f"  {job_id}:\n    runs-on: ubuntu-latest\n"
        if marker not in existing:
            existing += marker
        workflows[path] = existing
    return workflows


def _validate(
    *,
    candidate_sha: str = CANDIDATE,
    head_sha: str = CANDIDATE,
    policy: dict[str, object] | None = None,
    rulesets: list[object] | None = None,
    detail: dict[str, object] | None = None,
    workflows: dict[str, str] | None = None,
) -> dict[str, object]:
    return validate_snapshot(
        candidate_sha=candidate_sha,
        head_sha=head_sha,
        policy=_policy() if policy is None else policy,
        rulesets=_rulesets() if rulesets is None else rulesets,
        ruleset_detail=_detail() if detail is None else detail,
        workflow_texts=_workflows() if workflows is None else workflows,
    )


def _status_parameters(detail: dict[str, object]) -> dict[str, object]:
    rules = detail["rules"]
    assert isinstance(rules, list)
    for rule in rules:
        assert isinstance(rule, dict)
        if rule.get("type") == "required_status_checks":
            parameters = rule["parameters"]
            assert isinstance(parameters, dict)
            return parameters
    raise AssertionError("required_status_checks rule missing from fixture")


def test_h2_accepts_exact_candidate_and_canonical_merge_policy() -> None:
    detail = _detail()
    params = _status_parameters(detail)
    checks = params["required_status_checks"]
    assert isinstance(checks, list)
    checks.append({"context": "diagnostic-only", "integration_id": INTEGRATION_ID})

    evidence = _validate(detail=detail)

    assert evidence["schema"] == "lukart.hardcore-h2-evidence.v1"
    assert evidence["state"] == "CONTROL_PASS"
    assert evidence["candidate_sha"] == CANDIDATE
    assert evidence["policy_visibility"] == "CONFIRMED"
    assert evidence["bypass_actors"] == []
    assert evidence["additional_required_checks"] == [
        {"context": "diagnostic-only", "integration_id": INTEGRATION_ID}
    ]


def test_h2_rejects_candidate_head_mismatch() -> None:
    with pytest.raises(RuntimeError, match="exact-SHA mismatch"):
        _validate(head_sha="b" * 40)


def test_h2_rejects_missing_main_ruleset() -> None:
    with pytest.raises(RuntimeError, match="expected ruleset"):
        _validate(rulesets=[])


def test_h2_rejects_inactive_ruleset() -> None:
    rulesets = _rulesets()
    summary = rulesets[0]
    assert isinstance(summary, dict)
    summary["enforcement"] = "evaluate"
    with pytest.raises(RuntimeError, match="enforcement mismatch"):
        _validate(rulesets=rulesets)


def test_h2_rejects_undeclared_bypass_actor() -> None:
    detail = _detail()
    detail["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
    with pytest.raises(RuntimeError, match="undeclared bypass actors"):
        _validate(detail=detail)


def test_h2_rejects_non_strict_required_status_policy() -> None:
    detail = _detail()
    params = _status_parameters(detail)
    params["strict_required_status_checks_policy"] = False
    with pytest.raises(RuntimeError, match="strict required-status policy mismatch"):
        _validate(detail=detail)


def test_h2_rejects_missing_enterprise_gate() -> None:
    detail = _detail()
    params = _status_parameters(detail)
    checks = params["required_status_checks"]
    assert isinstance(checks, list)
    params["required_status_checks"] = [
        item
        for item in checks
        if isinstance(item, dict) and item.get("context") != "enterprise-gate"
    ]
    with pytest.raises(RuntimeError, match="enterprise-gate@15368"):
        _validate(detail=detail)


def test_h2_rejects_missing_codeql_gate() -> None:
    detail = _detail()
    params = _status_parameters(detail)
    checks = params["required_status_checks"]
    assert isinstance(checks, list)
    params["required_status_checks"] = [
        item
        for item in checks
        if isinstance(item, dict) and item.get("context") != "codeql"
    ]
    with pytest.raises(RuntimeError, match="codeql@15368"):
        _validate(detail=detail)


def test_h2_rejects_wrong_check_provider_identity() -> None:
    detail = _detail()
    params = _status_parameters(detail)
    checks = params["required_status_checks"]
    assert isinstance(checks, list)
    for item in checks:
        assert isinstance(item, dict)
        if item.get("context") == "codeql":
            item["integration_id"] = 999
    with pytest.raises(RuntimeError, match="codeql@15368"):
        _validate(detail=detail)


def test_h2_rejects_missing_canonical_workflow_job_identity() -> None:
    workflows = _workflows()
    path = ".github/workflows/enterprise-hardening.yml"
    workflows[path] = workflows[path].replace(
        "\n  enterprise-gate:\n",
        "\n  renamed-enterprise-gate:\n",
    )
    with pytest.raises(RuntimeError, match="job identity is missing"):
        _validate(workflows=workflows)


def test_h2_rejects_required_check_workflow_without_pr_trigger() -> None:
    workflows = _workflows()
    path = ".github/workflows/codeql-enterprise.yml"
    workflows[path] = workflows[path].replace("  pull_request:\n", "")
    with pytest.raises(RuntimeError, match="lacks pull_request trigger"):
        _validate(workflows=workflows)
