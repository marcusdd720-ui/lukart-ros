from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.solo_maintainer_governance_gate import (
    classify_change,
    validate_attestation,
    validate_exact_critical_paths,
    validate_profile,
    validate_technical_checks,
)

OWNER = "marcusdd720-ui"
SHA = "a" * 40


def _profile() -> dict[str, object]:
    return {
        "maintainer_id": OWNER,
        "independent_external_review": "NOT_PERFORMED",
        "attestation": {
            "marker": "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
            "decision": "ACCEPT",
            "revocation_decision": "REVOKE",
            "must_bind_current_head": True,
            "must_follow_terminal_technical_success": True,
            "author_association": "OWNER",
        },
        "cooldown_seconds": {
            "ordinary": 0,
            "critical": 7200,
            "governance": 86400,
        },
        "target_pull_request_rule": {
            "minimum_approving_review_count": 0,
            "dismiss_stale_reviews_on_push": True,
            "require_code_owner_review": False,
            "require_last_push_approval": False,
            "required_review_thread_resolution": True,
            "require_extra_approval_for_unattributed_changes": False,
            "allowed_merge_methods": ["merge"],
        },
        "required_solo_check": {
            "context": "solo-governance",
            "integration_id": 15368,
            "workflow": ".github/workflows/solo-maintainer-governance.yml",
            "job_id": "solo-governance",
        },
        "governance_paths": [
            "config/**",
            ".github/workflows/**",
            "scripts/solo_maintainer_governance_gate.py",
        ],
        "governance_support_paths": [
            "config/**",
            ".github/workflows/**",
            "scripts/solo_maintainer_governance_gate.py",
            "tests/test_solo_maintainer_governance_gate.py",
            "docs/REPOSITORY_GOVERNANCE.md",
        ],
    }


def _check(
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    started_at: str = "2026-09-14T10:00:00Z",
    completed_at: str = "2026-09-14T10:05:00Z",
    check_id: int = 1,
) -> dict[str, object]:
    return {
        "id": check_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at,
    }


def _comment(
    *,
    decision: str = "ACCEPT",
    sha: str = SHA,
    risk_class: str = "ordinary",
    created_at: str = "2026-09-14T10:06:00Z",
    comment_id: int = 1,
    login: str = OWNER,
    association: str = "OWNER",
) -> dict[str, object]:
    return {
        "id": comment_id,
        "created_at": created_at,
        "author_association": association,
        "user": {"login": login},
        "body": "\n".join(
            [
                "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
                f"candidate_sha: {sha}",
                f"decision: {decision}",
                "independent_external_review: NOT_PERFORMED",
                f"risk_class: {risk_class}",
            ]
        ),
    }


def test_profile_is_truthful_and_hardened() -> None:
    result = validate_profile(_profile())
    assert result["maintainer_id"] == OWNER
    assert result["cooldown_seconds"] == {
        "ordinary": 0,
        "critical": 7200,
        "governance": 86400,
    }


def test_profile_rejects_false_independent_review_claim() -> None:
    profile = _profile()
    profile["independent_external_review"] = "PASS"
    with pytest.raises(RuntimeError, match="NOT_PERFORMED"):
        validate_profile(profile)


def test_profile_rejects_weaker_governance_cooldown() -> None:
    profile = _profile()
    profile["cooldown_seconds"]["governance"] = 0  # type: ignore[index]
    with pytest.raises(RuntimeError, match="86400"):
        validate_profile(profile)


def test_classifies_governance_and_rejects_mixed_product_change() -> None:
    profile = validate_profile(_profile())
    with pytest.raises(RuntimeError, match="topology"):
        classify_change(
            [
                "config/enterprise_v1.json",
                "core/case_ledger.py",
            ],
            critical_paths=["core/case_ledger.py", "config/**"],
            governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
            governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
        )


def test_classifies_critical_and_ordinary_changes() -> None:
    profile = validate_profile(_profile())
    critical = classify_change(
        ["core/case_ledger.py"],
        critical_paths=["core/case_ledger.py"],
        governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
        governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
    )
    ordinary = classify_change(
        ["README.md"],
        critical_paths=["core/case_ledger.py"],
        governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
        governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
    )
    assert critical == "critical"
    assert ordinary == "ordinary"


def test_exact_critical_path_must_exist(tmp_path: Path) -> None:
    existing = tmp_path / "SECURITY.md"
    existing.write_text("policy\n", encoding="utf-8")
    assert validate_exact_critical_paths(
        tmp_path,
        ["SECURITY.md", "core/**"],
    ) == ["SECURITY.md"]
    with pytest.raises(RuntimeError, match="missing"):
        validate_exact_critical_paths(
            tmp_path,
            ["SECURITY.md", "docs/REPOSITORY_GOVERNANCE.md"],
        )


def test_technical_checks_require_latest_terminal_success() -> None:
    runs = [
        _check("gate", conclusion="failure", check_id=1),
        _check(
            "gate",
            check_id=2,
            started_at="2026-09-14T10:10:00Z",
            completed_at="2026-09-14T10:15:00Z",
        ),
        _check(
            "codeql",
            check_id=3,
            started_at="2026-09-14T10:11:00Z",
            completed_at="2026-09-14T10:16:00Z",
        ),
    ]
    ready_at = validate_technical_checks(
        runs,
        required_contexts=["gate", "codeql", "solo-governance"],
        self_context="solo-governance",
    )
    assert ready_at == datetime(2026, 9, 14, 10, 16, tzinfo=UTC)


def test_technical_checks_fail_closed_on_missing_context() -> None:
    with pytest.raises(RuntimeError, match="missing"):
        validate_technical_checks(
            [_check("gate")],
            required_contexts=["gate", "codeql", "solo-governance"],
            self_context="solo-governance",
        )


def test_attestation_binds_owner_head_risk_and_ready_time() -> None:
    result = validate_attestation(
        [_comment()],
        candidate_sha=SHA,
        maintainer_id=OWNER,
        risk_class="ordinary",
        technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
        cooldown_seconds=0,
    )
    assert result["comment_id"] == 1
    assert result["independent_external_review"] == "NOT_PERFORMED"


def test_attestation_rejects_early_governance_acceptance() -> None:
    with pytest.raises(RuntimeError, match="cooldown"):
        validate_attestation(
            [
                _comment(
                    risk_class="governance",
                    created_at="2026-09-15T09:00:00Z",
                )
            ],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="governance",
            technical_ready_at=datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
            cooldown_seconds=86400,
        )


def test_latest_revocation_overrides_prior_acceptance() -> None:
    with pytest.raises(RuntimeError, match="not ACCEPT"):
        validate_attestation(
            [
                _comment(comment_id=1, created_at="2026-09-14T10:06:00Z"),
                _comment(
                    decision="REVOKE",
                    comment_id=2,
                    created_at="2026-09-14T10:07:00Z",
                ),
            ],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )


def test_attestation_from_non_owner_is_ignored() -> None:
    with pytest.raises(RuntimeError, match="missing"):
        validate_attestation(
            [_comment(login="someone-else")],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )
