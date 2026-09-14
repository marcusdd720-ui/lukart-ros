from __future__ import annotations

from typing import cast

import pytest

from scripts.repository_governance_integrity_gate import (
    validate_bypass_governance,
    validate_repository_merge_settings,
    validate_review_governance,
    validate_signed_commit_enforcement_guard,
)


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


def _candidate_commit(*, verified: bool, reason: str) -> dict[str, object]:
    return {"commit": {"verification": {"verified": verified, "reason": reason}}}


def _rules(detail: dict[str, object]) -> list[object]:
    return cast(list[object], detail["rules"])


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
    params = detail["rules"][0]["parameters"]  # type: ignore[index]
    params["allowed_merge_methods"] = ["merge", "squash"]  # type: ignore[index]
    with pytest.raises(RuntimeError, match="allowed_merge_methods"):
        validate_review_governance(_policy(), detail)


def test_rejects_weak_canonical_minimum() -> None:
    policy = _policy()
    h2 = policy["h2_repository_policy"]  # type: ignore[index]
    pr_rule = h2["pull_request_rule"]  # type: ignore[index]
    pr_rule["minimum_approving_review_count"] = 1  # type: ignore[index]
    with pytest.raises(RuntimeError, match="minimum approvals"):
        validate_review_governance(policy, _detail())


def test_accepts_snapshot_bound_bypass_when_token_cannot_see_live_field() -> None:
    h2 = {
        "allowed_bypass_actors": [],
        "privileged_ruleset_snapshot": {
            "ruleset_id": 22352216,
            "ruleset_updated_at": "2026-09-06T13:52:14.880Z",
            "bypass_actors": [],
        },
    }
    detail = {"updated_at": "2026-09-06T13:52:14.880Z"}
    assert validate_bypass_governance(h2, detail, ruleset_id=22352216) == []


def test_rejects_stale_privileged_bypass_snapshot() -> None:
    h2 = {
        "allowed_bypass_actors": [],
        "privileged_ruleset_snapshot": {
            "ruleset_id": 22352216,
            "ruleset_updated_at": "old",
            "bypass_actors": [],
        },
    }
    detail = {"updated_at": "new"}
    with pytest.raises(RuntimeError, match="SNAPSHOT_STALE"):
        validate_bypass_governance(h2, detail, ruleset_id=22352216)


def test_allows_unsigned_candidate_before_signature_enforcement() -> None:
    evidence = validate_signed_commit_enforcement_guard(
        _detail(),
        _candidate_commit(verified=False, reason="unsigned"),
    )
    assert evidence["required_signatures_enforced"] is False
    assert evidence["candidate_commit_verified"] is False
    assert evidence["candidate_commit_verification_reason"] == "unsigned"


def test_rejects_signature_enforcement_when_candidate_path_is_unsigned() -> None:
    detail = _detail()
    _rules(detail).append({"type": "required_signatures"})
    with pytest.raises(RuntimeError, match="premature signing enforcement"):
        validate_signed_commit_enforcement_guard(
            detail,
            _candidate_commit(verified=False, reason="unsigned"),
        )


def test_accepts_signature_enforcement_after_verified_candidate() -> None:
    detail = _detail()
    _rules(detail).append({"type": "required_signatures"})
    evidence = validate_signed_commit_enforcement_guard(
        detail,
        _candidate_commit(verified=True, reason="valid"),
    )
    assert evidence["required_signatures_enforced"] is True
    assert evidence["candidate_commit_verified"] is True


def test_accepts_repository_merge_settings_from_canonical_policy() -> None:
    repository = {
        "allow_merge_commit": True,
        "allow_squash_merge": False,
        "allow_rebase_merge": False,
    }
    evidence = validate_repository_merge_settings(_policy(), repository)
    assert evidence == repository


def test_rejects_repository_merge_settings_broader_than_policy() -> None:
    repository = {
        "allow_merge_commit": True,
        "allow_squash_merge": True,
        "allow_rebase_merge": False,
    }
    with pytest.raises(RuntimeError, match="allow_squash_merge"):
        validate_repository_merge_settings(_policy(), repository)
