from __future__ import annotations

import pytest

from scripts.repository_governance_integrity_gate import validate_review_governance


def _policy() -> dict[str, object]:
    return {
        "h2_repository_policy": {
            "pull_request_rule": {
                "minimum_approving_review_count": 2,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
                "require_last_push_approval": True,
                "required_review_thread_resolution": True,
                "require_extra_approval_for_unattributed_changes": True,
                "allowed_merge_methods": ["merge"],
            },
            "review_integrity": {
                "ordinary_minimum_independent_approvals": 2,
                "critical_minimum_independent_approvals": 2,
                "approvals_must_bind_current_head": True,
                "critical_paths": ["core/**"],
            },
        }
    }


def _detail() -> dict[str, object]:
    return {
        "rules": [
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 2,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": True,
                    "require_last_push_approval": True,
                    "required_review_thread_resolution": True,
                    "require_extra_approval_for_unattributed_changes": True,
                    "allowed_merge_methods": ["merge"],
                },
            }
        ]
    }


def test_accepts_hardened_native_review_governance() -> None:
    evidence = validate_review_governance(_policy(), _detail())
    assert evidence["required_approving_review_count"] == 2
    assert evidence["allowed_merge_methods"] == ["merge"]


@pytest.mark.parametrize(
    "field",
    [
        "dismiss_stale_reviews_on_push",
        "require_code_owner_review",
        "require_last_push_approval",
        "required_review_thread_resolution",
        "require_extra_approval_for_unattributed_changes",
    ],
)
def test_rejects_disabled_review_integrity_control(field: str) -> None:
    detail = _detail()
    params = detail["rules"][0]["parameters"]  # type: ignore[index]
    params[field] = False  # type: ignore[index]
    with pytest.raises(RuntimeError, match=field):
        validate_review_governance(_policy(), detail)


def test_rejects_insufficient_approval_floor() -> None:
    detail = _detail()
    detail["rules"][0]["parameters"]["required_approving_review_count"] = 1  # type: ignore[index]
    with pytest.raises(RuntimeError, match="approvals"):
        validate_review_governance(_policy(), detail)


def test_accepts_stronger_approval_floor() -> None:
    detail = _detail()
    detail["rules"][0]["parameters"]["required_approving_review_count"] = 3  # type: ignore[index]
    evidence = validate_review_governance(_policy(), detail)
    assert evidence["required_approving_review_count"] == 3


def test_rejects_extra_merge_methods() -> None:
    detail = _detail()
    detail["rules"][0]["parameters"]["allowed_merge_methods"] = ["merge", "squash"]  # type: ignore[index]
    with pytest.raises(RuntimeError, match="allowed_merge_methods"):
        validate_review_governance(_policy(), detail)


def test_rejects_weak_canonical_minimum() -> None:
    policy = _policy()
    policy["h2_repository_policy"]["pull_request_rule"]["minimum_approving_review_count"] = 1  # type: ignore[index]
    with pytest.raises(RuntimeError, match="minimum approvals"):
        validate_review_governance(policy, _detail())
