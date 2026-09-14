from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
API_ROOT = "https://api.github.com/repos"
GRAPHQL_API = "https://api.github.com/graphql"


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a list")
    return cast(list[object], value)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _github_json(url: str, *, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lukart-ros-governance-integrity",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(f"GOVERNANCE_VISIBILITY_UNKNOWN: cannot read {url}: {exc}") from exc


def _github_graphql(
    query: str,
    variables: Mapping[str, object],
    *,
    token: str | None,
) -> Mapping[str, object]:
    if not token:
        raise RuntimeError(
            "GOVERNANCE_VISIBILITY_UNKNOWN: GitHub token required for GraphQL repository settings"
        )
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lukart-ros-governance-integrity",
        "Authorization": f"Bearer {token}",
    }
    body = json.dumps({"query": query, "variables": dict(variables)}).encode("utf-8")
    request = urllib.request.Request(GRAPHQL_API, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = _mapping(
                json.loads(response.read().decode("utf-8")),
                label="GitHub GraphQL response",
            )
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            f"GOVERNANCE_VISIBILITY_UNKNOWN: cannot read {GRAPHQL_API}: {exc}"
        ) from exc
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(
            "GOVERNANCE_VISIBILITY_UNKNOWN: GitHub GraphQL repository settings query failed"
        )
    return _mapping(payload.get("data"), label="GitHub GraphQL data")


def _find_ruleset(rulesets: list[object], *, name: str, target: str) -> Mapping[str, object]:
    for index, item in enumerate(rulesets):
        candidate = _mapping(item, label=f"rulesets[{index}]")
        if candidate.get("name") == name and candidate.get("target") == target:
            return candidate
    raise RuntimeError(f"governance drift: ruleset {name!r} target={target!r} is missing")


def _rule(rules: list[object], rule_type: str) -> Mapping[str, object]:
    for index, item in enumerate(rules):
        candidate = _mapping(item, label=f"rules[{index}]")
        if candidate.get("type") == rule_type:
            return candidate
    raise RuntimeError(f"governance drift: rule {rule_type!r} is missing")


def _resolve_repository_merge_settings(
    repository: str,
    repository_detail: Mapping[str, object],
    *,
    token: str | None,
) -> Mapping[str, object]:
    rest_fields = (
        "allow_merge_commit",
        "allow_squash_merge",
        "allow_rebase_merge",
    )
    if all(isinstance(repository_detail.get(field), bool) for field in rest_fields):
        return repository_detail

    if repository.count("/") != 1:
        raise RuntimeError("governance policy identity is incomplete")
    owner, name = repository.split("/", 1)
    query = """
    query RepositoryMergeSettings($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        mergeCommitAllowed
        squashMergeAllowed
        rebaseMergeAllowed
      }
    }
    """
    data = _github_graphql(query, {"owner": owner, "name": name}, token=token)
    graphql_repository = _mapping(
        data.get("repository"),
        label="GitHub GraphQL repository",
    )
    graphql_fields = {
        "allow_merge_commit": "mergeCommitAllowed",
        "allow_squash_merge": "squashMergeAllowed",
        "allow_rebase_merge": "rebaseMergeAllowed",
    }
    resolved: dict[str, object] = {}
    for rest_field, graphql_field in graphql_fields.items():
        value = graphql_repository.get(graphql_field)
        if not isinstance(value, bool):
            raise RuntimeError(
                "GOVERNANCE_VISIBILITY_UNKNOWN: repository merge setting "
                f"{rest_field} unavailable via REST and GraphQL"
            )
        resolved[rest_field] = value
    return resolved


def validate_bypass_governance(
    h2: Mapping[str, object],
    detail: Mapping[str, object],
    *,
    ruleset_id: int,
) -> list[object]:
    allowed = _list(h2.get("allowed_bypass_actors"), label="h2.allowed_bypass_actors")
    live = detail.get("bypass_actors")
    if live is not None:
        if not isinstance(live, list):
            raise RuntimeError("governance visibility unknown: malformed bypass_actors")
        if live != allowed:
            raise RuntimeError(
                f"governance drift: bypass actors actual={live!r} expected={allowed!r}"
            )
        return live

    snapshot = _mapping(
        h2.get("privileged_ruleset_snapshot"),
        label="h2.privileged_ruleset_snapshot",
    )
    snapshot_bypass = _list(
        snapshot.get("bypass_actors"),
        label="h2.privileged_ruleset_snapshot.bypass_actors",
    )
    if snapshot.get("ruleset_id") != ruleset_id:
        raise RuntimeError("GOVERNANCE_SNAPSHOT_STALE: ruleset ID mismatch")
    live_updated_at = detail.get("updated_at")
    snapshot_updated_at = snapshot.get("ruleset_updated_at")
    if not isinstance(live_updated_at, str) or not live_updated_at:
        raise RuntimeError("GOVERNANCE_VISIBILITY_UNKNOWN: ruleset updated_at missing")
    if snapshot_updated_at != live_updated_at:
        raise RuntimeError(
            "GOVERNANCE_SNAPSHOT_STALE: live ruleset changed after privileged snapshot"
        )
    if snapshot_bypass != allowed:
        raise RuntimeError("governance policy conflict: snapshot bypass differs from policy")
    return snapshot_bypass


def validate_signed_commit_enforcement_guard(
    detail: Mapping[str, object],
    candidate_commit: Mapping[str, object],
) -> dict[str, object]:
    rules = _list(detail.get("rules"), label="ruleset.rules")
    signatures_enforced = any(
        _mapping(item, label=f"rules[{index}]").get("type") == "required_signatures"
        for index, item in enumerate(rules)
    )
    commit = _mapping(candidate_commit.get("commit"), label="candidate_commit.commit")
    verification = _mapping(commit.get("verification"), label="candidate_commit.verification")
    verified = verification.get("verified")
    reason = verification.get("reason")
    if not isinstance(verified, bool):
        raise RuntimeError("governance visibility unknown: candidate commit verification missing")
    if signatures_enforced and not verified:
        raise RuntimeError(
            "premature signing enforcement: required_signatures is active while the "
            f"candidate commit is not verified (reason={reason!r})"
        )
    return {
        "required_signatures_enforced": signatures_enforced,
        "candidate_commit_verified": verified,
        "candidate_commit_verification_reason": reason,
    }


def validate_review_governance(
    policy: Mapping[str, object],
    detail: Mapping[str, object],
) -> dict[str, object]:
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    expected = _mapping(h2.get("pull_request_rule"), label="h2.pull_request_rule")
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    rules = _list(detail.get("rules"), label="ruleset.rules")
    params = _mapping(
        _rule(rules, "pull_request").get("parameters"),
        label="pull_request.parameters",
    )

    minimum = expected.get("minimum_approving_review_count")
    actual = params.get("required_approving_review_count")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 2:
        raise RuntimeError("governance policy conflict: minimum approvals must be >= 2")
    if not isinstance(actual, int) or isinstance(actual, bool) or actual < minimum:
        raise RuntimeError(f"governance drift: approvals actual={actual!r} minimum={minimum}")

    for field in (
        "dismiss_stale_reviews_on_push",
        "require_code_owner_review",
        "require_last_push_approval",
        "required_review_thread_resolution",
        "require_extra_approval_for_unattributed_changes",
    ):
        if expected.get(field) is not True:
            raise RuntimeError(f"governance policy conflict: {field} must be true")
        if params.get(field) is not True:
            raise RuntimeError(f"governance drift: {field} is not enabled")

    allowed = expected.get("allowed_merge_methods")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) for x in allowed):
        raise RuntimeError(
            "governance policy conflict: allowed_merge_methods must be a non-empty string list"
        )
    actual_methods = params.get("allowed_merge_methods")
    if not isinstance(actual_methods, list) or set(actual_methods) != set(allowed):
        raise RuntimeError(
            "governance drift: allowed_merge_methods "
            f"actual={actual_methods!r} expected={allowed!r}"
        )

    ordinary = review.get("ordinary_minimum_independent_approvals")
    critical = review.get("critical_minimum_independent_approvals")
    if ordinary != minimum or critical != minimum:
        raise RuntimeError(
            "governance policy conflict: native approval floor must match review-integrity minima"
        )
    if review.get("approvals_must_bind_current_head") is not True:
        raise RuntimeError("governance policy conflict: approvals must bind current head")
    critical_paths = review.get("critical_paths")
    if not isinstance(critical_paths, list) or not critical_paths:
        raise RuntimeError("governance policy conflict: critical_paths must not be empty")

    return {
        "required_approving_review_count": actual,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": True,
        "require_last_push_approval": True,
        "required_review_thread_resolution": True,
        "require_extra_approval_for_unattributed_changes": True,
        "allowed_merge_methods": sorted(cast(list[str], actual_methods)),
    }


def validate_repository_merge_settings(
    policy: Mapping[str, object],
    repository_detail: Mapping[str, object],
) -> dict[str, bool]:
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    expected = _mapping(h2.get("pull_request_rule"), label="h2.pull_request_rule")
    allowed = expected.get("allowed_merge_methods")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) for x in allowed):
        raise RuntimeError(
            "governance policy conflict: allowed_merge_methods must be a non-empty string list"
        )
    supported = {
        "merge": "allow_merge_commit",
        "squash": "allow_squash_merge",
        "rebase": "allow_rebase_merge",
    }
    unknown = sorted(set(cast(list[str], allowed)) - set(supported))
    if unknown:
        raise RuntimeError(
            f"governance policy conflict: unsupported merge methods {unknown!r}"
        )

    evidence: dict[str, bool] = {}
    for method, field in supported.items():
        expected_enabled = method in allowed
        actual = repository_detail.get(field)
        if not isinstance(actual, bool):
            raise RuntimeError(f"governance visibility unknown: repository setting {field} missing")
        if actual is not expected_enabled:
            raise RuntimeError(
                "governance drift: repository merge setting "
                f"{field} actual={actual!r} expected={expected_enabled!r}"
            )
        evidence[field] = actual
    return evidence


def build_evidence(candidate_sha: str) -> dict[str, object]:
    head = _git("rev-parse", "HEAD")
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")
    policy = _mapping(
        json.loads(POLICY_PATH.read_text(encoding="utf-8")),
        label="enterprise policy",
    )
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    repository = str(h2.get("repository", ""))
    ruleset_name = str(h2.get("ruleset_name", ""))
    target = str(h2.get("target", ""))
    if not repository or not ruleset_name or not target:
        raise RuntimeError("governance policy identity is incomplete")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repository_detail = _mapping(
        _github_json(f"{API_ROOT}/{repository}", token=token),
        label="repository detail",
    )
    merge_settings_detail = _resolve_repository_merge_settings(
        repository,
        repository_detail,
        token=token,
    )
    inventory = _github_json(f"{API_ROOT}/{repository}/rulesets", token=token)
    rulesets = _list(inventory, label="rulesets")
    summary = _find_ruleset(rulesets, name=ruleset_name, target=target)
    ruleset_id = summary.get("id")
    if not isinstance(ruleset_id, int):
        raise RuntimeError("governance visibility unknown: ruleset ID is missing")
    detail = _mapping(
        _github_json(f"{API_ROOT}/{repository}/rulesets/{ruleset_id}", token=token),
        label="ruleset detail",
    )
    if detail.get("enforcement") != "active":
        raise RuntimeError("governance drift: ruleset is not active")
    bypass = validate_bypass_governance(h2, detail, ruleset_id=ruleset_id)
    candidate_commit = _mapping(
        _github_json(f"{API_ROOT}/{repository}/commits/{candidate_sha}", token=token),
        label="candidate commit",
    )
    signing_evidence = validate_signed_commit_enforcement_guard(detail, candidate_commit)
    review_evidence = validate_review_governance(policy, detail)
    repository_merge_evidence = validate_repository_merge_settings(policy, merge_settings_detail)
    return {
        "schema": "lukart.repository-governance-integrity.v1",
        "candidate_sha": candidate_sha,
        "ruleset_id": ruleset_id,
        "bypass_actors": bypass,
        "signing_enforcement": signing_evidence,
        "review_rule": review_evidence,
        "repository_merge_settings": repository_merge_evidence,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed live repository review-governance gate"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="build/hardcore/repository-governance-integrity.json")
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha)
    except RuntimeError as exc:
        print(f"REPOSITORY_GOVERNANCE_INTEGRITY=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPOSITORY_GOVERNANCE_INTEGRITY=PASS")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"RULESET_ID={evidence['ruleset_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
