from __future__ import annotations

import pytest

from validation.release_governance import (
    REQUIRED_RELEASE_CHECKS,
    ReleaseGovernanceError,
    validate_effective_main_rules,
)


def _effective_rules() -> list[dict[str, object]]:
    return [
        {"type": "pull_request", "parameters": {}},
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": context}
                    for context in sorted(REQUIRED_RELEASE_CHECKS)
                ],
            },
        },
    ]


def test_release_governance_accepts_complete_effective_rules() -> None:
    validate_effective_main_rules(_effective_rules())


def test_release_governance_requires_pull_request_rule() -> None:
    rules = [rule for rule in _effective_rules() if rule["type"] != "pull_request"]

    with pytest.raises(ReleaseGovernanceError, match="pull_request"):
        validate_effective_main_rules(rules)


def test_release_governance_requires_strict_up_to_date_checks() -> None:
    rules = _effective_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["strict_required_status_checks_policy"] = False

    with pytest.raises(ReleaseGovernanceError, match="up to date"):
        validate_effective_main_rules(rules)


def test_release_governance_requires_program_gate_for_final_release() -> None:
    rules = _effective_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    raw_checks = parameters["required_status_checks"]
    assert isinstance(raw_checks, list)
    parameters["required_status_checks"] = [
        check
        for check in raw_checks
        if isinstance(check, dict) and check.get("context") != "program-gate"
    ]

    with pytest.raises(ReleaseGovernanceError, match="program-gate"):
        validate_effective_main_rules(rules)


def test_release_governance_requires_force_push_and_delete_guards() -> None:
    for missing_type in ("non_fast_forward", "deletion"):
        rules = [rule for rule in _effective_rules() if rule["type"] != missing_type]

        with pytest.raises(ReleaseGovernanceError, match=missing_type):
            validate_effective_main_rules(rules)
