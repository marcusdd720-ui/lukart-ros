from __future__ import annotations

import pytest

from scripts.solo_attestation_integrity_guard import validate_direct_human_attestations

OWNER = "marcusdd720-ui"
SHA = "a" * 40


def _comment(
    *,
    login: str = OWNER,
    user_type: str = "User",
    created_at: str = "2026-09-14T10:00:00Z",
    updated_at: str = "2026-09-14T10:00:00Z",
    performed_via_github_app: object = None,
) -> dict[str, object]:
    return {
        "id": 1,
        "created_at": created_at,
        "updated_at": updated_at,
        "author_association": "OWNER",
        "performed_via_github_app": performed_via_github_app,
        "user": {"login": login, "type": user_type},
        "body": "\n".join(
            [
                "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
                f"candidate_sha: {SHA}",
                "decision: ACCEPT",
                "independent_external_review: NOT_PERFORMED",
                "risk_class: governance",
            ]
        ),
    }


def test_accepts_unedited_direct_owner_comment() -> None:
    evidence = validate_direct_human_attestations(
        [_comment()],
        candidate_sha=SHA,
        maintainer_id=OWNER,
    )
    assert evidence["direct_human_attestation_comment_ids"] == [1]


def test_rejects_app_mediated_attestation() -> None:
    with pytest.raises(RuntimeError, match="GitHub App"):
        validate_direct_human_attestations(
            [_comment(performed_via_github_app={"slug": "automation"})],
            candidate_sha=SHA,
            maintainer_id=OWNER,
        )


def test_rejects_edited_attestation() -> None:
    with pytest.raises(RuntimeError, match="edited"):
        validate_direct_human_attestations(
            [
                _comment(
                    updated_at="2026-09-14T10:05:00Z",
                )
            ],
            candidate_sha=SHA,
            maintainer_id=OWNER,
        )


def test_rejects_bot_actor() -> None:
    with pytest.raises(RuntimeError, match="human GitHub User"):
        validate_direct_human_attestations(
            [_comment(user_type="Bot")],
            candidate_sha=SHA,
            maintainer_id=OWNER,
        )


def test_ignores_non_owner_and_fails_closed_without_owner_attestation() -> None:
    with pytest.raises(RuntimeError, match="missing"):
        validate_direct_human_attestations(
            [_comment(login="someone-else")],
            candidate_sha=SHA,
            maintainer_id=OWNER,
        )
