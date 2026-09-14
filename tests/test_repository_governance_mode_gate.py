from __future__ import annotations

import pytest

from scripts.repository_governance_mode_gate import (
    validate_required_status_checks,
    validate_solo_review_governance,
)


def _h2() -> dict[str, object]:
    return {
        "required_rule_types": [
            "deletion",
            "non_fast_forward",
            "pull_request",
            "required_status_checks",
        ],
        "default_branch_condition": "~DEFAULT_BRANCH",
        "strict_required_status_checks": True,
        "do_not_enforce_on_create": False,
        "required_checks": [
            {"context": "gate", "integration_id": 15368},
            {"context": "solo-governance", "integration_id": 15368},
        ],
        "solo_maintainer_profile": {
            "target_pull_request_rule": {
                "minimum_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
                "require_extra_approval_for_unattributed_changes": False,
                "allowed_merge_methods": ["merge"],
            }
        },
        "review_integrity": {
            "ordinary_minimum_independent_approvals": 0,
            "critical_minimum_independent_approvals": 0,
            "independent_external_review": "NOT_PERFORMED",
            "maintainer_attestation_must_bind_current_head": True,
        },
    }


def _detail() -> dict[str, object]:
    return {
        "conditions": {
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True,
                    "require_extra_approval_for_unattributed_changes": False,
                    "allowed_merge_methods": ["merge"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {"context": "gate", "integration_id": 15368},
                        {"context": "solo-governance", "integration_id": 15368},
                    ],
                },
            },
        ],
    }


def test_required_status_checks_accept_exact_canonical_live_state() -> None:
    evidence = validate_required_status_checks(_h2(), _detail())
    assert evidence["strict"] is True
    assert evidence["required_checks"] == ["gate", "solo-governance"]


def test_required_status_checks_reject_missing_check() -> None:
    detail = _detail()
    detail["rules"][3]["parameters"]["required_status_checks"] = [  # type: ignore[index]
        {"context": "gate", "integration_id": 15368}
    ]
    with pytest.raises(RuntimeError, match="differ from canonical"):
        validate_required_status_checks(_h2(), detail)


def test_required_status_checks_reject_unapproved_extra_check() -> None:
    detail = _detail()
    detail["rules"][3]["parameters"]["required_status_checks"].append(  # type: ignore[index]
        {"context": "spoof", "integration_id": 15368}
    )
    with pytest.raises(RuntimeError, match="differ from canonical"):
        validate_required_status_checks(_h2(), detail)


def test_required_status_checks_reject_non_strict_live_policy() -> None:
    detail = _detail()
    detail["rules"][3]["parameters"]["strict_required_status_checks_policy"] = False  # type: ignore[index]
    with pytest.raises(RuntimeError, match="strict required status checks"):
        validate_required_status_checks(_h2(), detail)


def test_required_status_checks_reject_branch_condition_drift() -> None:
    detail = _detail()
    detail["conditions"]["ref_name"]["include"] = ["refs/heads/dev"]  # type: ignore[index]
    with pytest.raises(RuntimeError, match="branch condition"):
        validate_required_status_checks(_h2(), detail)


def test_solo_review_accepts_zero_native_approvals_and_compensating_shape() -> None:
    evidence = validate_solo_review_governance(_h2(), _detail())
    assert evidence["minimum_approving_review_count"] == 0
    assert evidence["require_code_owner_review"] is False
    assert evidence["required_review_thread_resolution"] is True


def test_solo_review_rejects_native_approval_drift() -> None:
    detail = _detail()
    detail["rules"][2]["parameters"]["required_approving_review_count"] = 1  # type: ignore[index]
    with pytest.raises(RuntimeError, match="minimum_approving_review_count"):
        validate_solo_review_governance(_h2(), detail)


def test_solo_review_rejects_codeowner_requirement() -> None:
    detail = _detail()
    detail["rules"][2]["parameters"]["require_code_owner_review"] = True  # type: ignore[index]
    with pytest.raises(RuntimeError, match="require_code_owner_review"):
        validate_solo_review_governance(_h2(), detail)


def test_solo_review_rejects_false_independent_review_state() -> None:
    h2 = _h2()
    h2["review_integrity"]["independent_external_review"] = "PASS"  # type: ignore[index]
    with pytest.raises(RuntimeError, match="NOT_PERFORMED"):
        validate_solo_review_governance(h2, _detail())


def test_solo_review_requires_head_bound_attestation_contract() -> None:
    h2 = _h2()
    h2["review_integrity"]["maintainer_attestation_must_bind_current_head"] = False  # type: ignore[index]
    with pytest.raises(RuntimeError, match="head-bound"):
        validate_solo_review_governance(h2, _detail())
