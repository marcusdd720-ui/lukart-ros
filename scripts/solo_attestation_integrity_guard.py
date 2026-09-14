from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import scripts.repository_governance_transition_gate as transition
import scripts.solo_maintainer_governance_gate as solo

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def validate_direct_human_attestations(
    comments: list[object],
    *,
    candidate_sha: str,
    maintainer_id: str,
) -> dict[str, object]:
    candidate_sha = solo.validate_candidate_sha(candidate_sha)
    matches: list[int] = []
    for index, raw in enumerate(comments):
        comment = _mapping(raw, label=f"comments[{index}]")
        fields = solo._attestation_fields(comment.get("body"))
        if fields is None or fields.get("candidate_sha") != candidate_sha:
            continue
        user = _mapping(comment.get("user"), label=f"comments[{index}].user")
        if user.get("login") != maintainer_id:
            continue
        if comment.get("author_association") != "OWNER":
            raise RuntimeError("solo attestation author association must be OWNER")
        if user.get("type") != "User":
            raise RuntimeError("solo attestation actor must be a human GitHub User")
        if comment.get("performed_via_github_app") is not None:
            raise RuntimeError(
                "solo attestation must be posted directly by the maintainer, not via GitHub App"
            )
        created_at = comment.get("created_at")
        updated_at = comment.get("updated_at")
        if not isinstance(created_at, str) or not isinstance(updated_at, str):
            raise RuntimeError("solo attestation timestamps are missing")
        if created_at != updated_at:
            raise RuntimeError(
                "solo attestation comment was edited; post a new unedited attestation instead"
            )
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool):
            raise RuntimeError("solo attestation comment id must be an integer")
        matches.append(comment_id)
    if not matches:
        raise RuntimeError("direct maintainer attestation for current head is missing")
    return {"direct_human_attestation_comment_ids": sorted(matches)}


def build_evidence(candidate_sha: str) -> dict[str, object]:
    candidate_sha = solo.validate_candidate_sha(candidate_sha)
    try:
        policy = _mapping(
            json.loads(POLICY_PATH.read_text(encoding="utf-8")),
            label="enterprise policy",
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("enterprise policy must be valid UTF-8 JSON") from exc
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    transition.validate_state_machine(h2)
    transition.validate_state_contract(h2)
    transition.validate_profile_truthfulness(h2)
    state = h2.get("governance_state")
    if state not in transition.STATES:
        raise RuntimeError(f"unsupported governance_state {state!r}")
    if state != "SOLO_ACTIVE":
        return {
            "schema": "lukart.solo-attestation-integrity.v1",
            "candidate_sha": candidate_sha,
            "governance_state": state,
            "mode": "NOT_REQUIRED_UNTIL_SOLO_ACTIVE",
            "state": "DORMANT_PASS" if state == "INDEPENDENT_LOCKED" else "ARMED_PASS",
        }

    profile = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    maintainer_id = profile.get("maintainer_id")
    repository = h2.get("repository")
    if not isinstance(maintainer_id, str) or not maintainer_id:
        raise RuntimeError("solo maintainer identity is missing")
    if not isinstance(repository, str) or not repository:
        raise RuntimeError("repository identity is missing")
    raw_pr = os.environ.get("PR_NUMBER")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not raw_pr or not raw_pr.isdigit() or int(raw_pr) <= 0:
        raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: PR_NUMBER is required")
    if not token:
        raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: GitHub token is required")
    comments = solo._github_list(
        f"{solo.API_ROOT}/{repository}/issues/{int(raw_pr)}/comments",
        token=token,
    )
    evidence = validate_direct_human_attestations(
        comments,
        candidate_sha=candidate_sha,
        maintainer_id=maintainer_id,
    )
    return {
        "schema": "lukart.solo-attestation-integrity.v1",
        "candidate_sha": candidate_sha,
        "governance_state": state,
        "mode": "SOLO_ACTIVE",
        **evidence,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject edited or app-mediated solo-maintainer attestations"
    )
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha)
    except RuntimeError as exc:
        print(f"SOLO_ATTESTATION_INTEGRITY=FAIL: {exc}")
        return 1
    print(f"SOLO_ATTESTATION_INTEGRITY={evidence['state']}")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
