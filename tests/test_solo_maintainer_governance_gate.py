from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import scripts.solo_maintainer_governance_gate as solo_gate
from scripts.solo_maintainer_governance_gate import (
    build_candidate_check_runs_url,
    classify_change,
    validate_attestation,
    validate_candidate_sha,
    validate_exact_critical_paths,
    validate_profile,
    validate_technical_checks,
)

OWNER = "marcusdd720-ui"
SHA = "a" * 40
OTHER_SHA = "b" * 40


def _profile() -> dict[str, object]:
    return {
        "maintainer_id": OWNER,
        "default_branch": "main",
        "independent_external_review": "NOT_PERFORMED",
        "reviewer_independent": False,
        "attestation": {
            "marker": "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
            "decision": "ACCEPT",
            "revocation_decision": "REVOKE",
            "must_bind_current_head": True,
            "must_follow_terminal_technical_success": True,
            "author_association": "OWNER",
        },
        "cooldown_seconds": {"ordinary": 0, "critical": 7200, "governance": 86400},
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
    head_sha: str = SHA,
    app_id: int = 15368,
) -> dict[str, object]:
    return {
        "id": check_id,
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at,
        "app": {"id": app_id},
    }


def _comment(
    *,
    decision: str = "ACCEPT",
    sha: str = SHA,
    risk_class: str = "ordinary",
    created_at: str = "2026-09-14T10:06:00Z",
    updated_at: str | None = None,
    comment_id: int = 1,
    login: str = OWNER,
    association: str = "OWNER",
    user_type: str = "User",
    app: object = None,
) -> dict[str, object]:
    return {
        "id": comment_id,
        "created_at": created_at,
        "updated_at": updated_at or created_at,
        "author_association": association,
        "performed_via_github_app": app,
        "user": {"login": login, "type": user_type},
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


def test_candidate_sha_requires_exact_40_hex() -> None:
    assert validate_candidate_sha("A" * 40) == "a" * 40
    for value in ("a" * 39, "a" * 41, "g" * 40, "a" * 39 + "?", "{sha}"):
        with pytest.raises(RuntimeError, match="40 hexadecimal"):
            validate_candidate_sha(value)


def test_exact_check_runs_url_rejects_path_query_and_placeholder_injection() -> None:
    expected = (
        "https://api.github.com/repos/owner/repo/commits/"
        + SHA
        + "/check-runs?filter=latest&per_page=100&page=2"
    )
    assert build_candidate_check_runs_url("owner/repo", SHA, page=2) == expected
    for candidate in (SHA[:-1] + "/", SHA[:-1] + "?", "{sha}" + "a" * 35):
        with pytest.raises(RuntimeError):
            build_candidate_check_runs_url("owner/repo", candidate, page=1)
    with pytest.raises(RuntimeError, match="owner/name"):
        build_candidate_check_runs_url("owner/repo?x=1", SHA, page=1)


def test_check_run_pagination_collects_all_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_json(url: str, *, token: str | None) -> object:
        seen.append(url)
        if url.endswith("&page=1"):
            return {"check_runs": [_check(f"check-{index}") for index in range(100)]}
        if url.endswith("&page=2"):
            return {"check_runs": [_check("last", check_id=101)]}
        raise AssertionError(url)

    monkeypatch.setattr(solo_gate, "_github_json", fake_json)
    result = solo_gate._github_check_runs("owner/repo", SHA, token="token")
    assert len(result) == 101
    assert len(seen) == 2


def test_check_run_pagination_rejects_data_for_different_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        solo_gate,
        "_github_json",
        lambda url, token=None: {"check_runs": [_check("gate", head_sha=OTHER_SHA)]},
    )
    with pytest.raises(RuntimeError, match="exact candidate SHA"):
        solo_gate._github_check_runs("owner/repo", SHA, token="token")


def test_profile_is_truthful_and_hardened() -> None:
    result = validate_profile(_profile())
    assert result["maintainer_id"] == OWNER
    assert result["default_branch"] == "main"
    assert result["reviewer_independent"] is False


def test_profile_rejects_false_independent_review_claim() -> None:
    profile = _profile()
    profile["independent_external_review"] = "PASS"
    with pytest.raises(RuntimeError, match="NOT_PERFORMED"):
        validate_profile(profile)


def test_profile_rejects_weaker_governance_cooldown() -> None:
    profile = _profile()
    profile["cooldown_seconds"]["governance"] = 0  # type: ignore[index]
    with pytest.raises(RuntimeError, match="cooldown"):
        validate_profile(profile)


def test_classifies_governance_and_rejects_mixed_product_change() -> None:
    profile = validate_profile(_profile())
    with pytest.raises(RuntimeError, match="topology"):
        classify_change(
            ["config/enterprise_v1.json", "core/case_ledger.py"],
            critical_paths=["core/case_ledger.py", "config/**"],
            governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
            governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
        )


def test_classifies_critical_and_ordinary_changes() -> None:
    profile = validate_profile(_profile())
    assert classify_change(
        ["core/case_ledger.py"],
        critical_paths=["core/case_ledger.py"],
        governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
        governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
    ) == "critical"
    assert classify_change(
        ["README.md"],
        critical_paths=["core/case_ledger.py"],
        governance_paths=profile["governance_paths"],  # type: ignore[arg-type]
        governance_support_paths=profile["governance_support_paths"],  # type: ignore[arg-type]
    ) == "ordinary"


def test_exact_critical_path_must_exist(tmp_path: Path) -> None:
    (tmp_path / "SECURITY.md").write_text("policy\n", encoding="utf-8")
    assert validate_exact_critical_paths(tmp_path, ["SECURITY.md"]) == ["SECURITY.md"]
    with pytest.raises(RuntimeError, match="missing"):
        validate_exact_critical_paths(tmp_path, ["docs/REPOSITORY_GOVERNANCE.md"])


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
        required_contexts=["gate", "codeql"],
        self_context="solo-governance",
        candidate_sha=SHA,
        required_integration_ids={"gate": 15368, "codeql": 15368},
    )
    assert ready_at == datetime(2026, 9, 14, 10, 16, tzinfo=UTC)


def test_technical_checks_reject_self_dependency() -> None:
    with pytest.raises(RuntimeError, match="self context"):
        validate_technical_checks(
            [_check("gate")],
            required_contexts=["gate", "solo-governance"],
            self_context="solo-governance",
            candidate_sha=SHA,
        )


def test_technical_checks_reject_wrong_sha_missing_and_wrong_integration() -> None:
    with pytest.raises(RuntimeError, match="exact candidate SHA"):
        validate_technical_checks(
            [_check("gate", head_sha=OTHER_SHA)],
            required_contexts=["gate"],
            self_context="solo-governance",
            candidate_sha=SHA,
        )
    with pytest.raises(RuntimeError, match="missing"):
        validate_technical_checks(
            [_check("gate")],
            required_contexts=["gate", "codeql"],
            self_context="solo-governance",
            candidate_sha=SHA,
        )
    with pytest.raises(RuntimeError, match="integration mismatch"):
        validate_technical_checks(
            [_check("gate", app_id=999)],
            required_contexts=["gate"],
            self_context="solo-governance",
            candidate_sha=SHA,
            required_integration_ids={"gate": 15368},
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
    assert result["reviewer_independent"] is False


def test_attestation_rejects_early_governance_acceptance() -> None:
    with pytest.raises(RuntimeError, match="cooldown"):
        validate_attestation(
            [_comment(risk_class="governance", created_at="2026-09-15T09:00:00Z")],
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
                _comment(decision="REVOKE", comment_id=2, created_at="2026-09-14T10:07:00Z"),
            ],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )


def test_attestation_rejects_edited_app_and_forged_association() -> None:
    with pytest.raises(RuntimeError, match="edited"):
        validate_attestation(
            [_comment(updated_at="2026-09-14T10:07:00Z")],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )
    with pytest.raises(RuntimeError, match="GitHub App"):
        validate_attestation(
            [_comment(app={"slug": "automation"})],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )
    with pytest.raises(RuntimeError, match="association"):
        validate_attestation(
            [_comment(association="MEMBER")],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )


def test_attestation_from_non_owner_and_stale_sha_do_not_satisfy_control() -> None:
    with pytest.raises(RuntimeError, match="missing"):
        validate_attestation(
            [_comment(login="someone-else"), _comment(sha=OTHER_SHA)],
            candidate_sha=SHA,
            maintainer_id=OWNER,
            risk_class="ordinary",
            technical_ready_at=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
            cooldown_seconds=0,
        )
