from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import scripts.repository_governance_integrity_gate as legacy

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a list")
    return cast(list[object], value)


def _rule(rules: list[object], rule_type: str) -> Mapping[str, object]:
    for index, raw in enumerate(rules):
        rule = _mapping(raw, label=f"rules[{index}]")
        if rule.get("type") == rule_type:
            return rule
    raise RuntimeError(f"governance drift: rule {rule_type!r} is missing")


def validate_required_status_checks(
    h2: Mapping[str, object],
    detail: Mapping[str, object],
) -> dict[str, object]:
    rules = _list(detail.get("rules"), label="ruleset.rules")
    actual_types = {
        str(_mapping(raw, label=f"rules[{index}]").get("type", ""))
        for index, raw in enumerate(rules)
    }
    expected_types_raw = h2.get("required_rule_types")
    if not isinstance(expected_types_raw, list) or any(
        not isinstance(item, str) or not item for item in expected_types_raw
    ):
        raise RuntimeError("governance policy conflict: required_rule_types must be strings")
    expected_types = set(cast(list[str], expected_types_raw))
    missing_types = sorted(expected_types - actual_types)
    if missing_types:
        raise RuntimeError(f"governance drift: required rules missing: {missing_types!r}")

    conditions = _mapping(detail.get("conditions"), label="ruleset.conditions")
    ref_name = _mapping(conditions.get("ref_name"), label="ruleset.conditions.ref_name")
    expected_branch = h2.get("default_branch_condition")
    if not isinstance(expected_branch, str) or not expected_branch:
        raise RuntimeError("governance policy conflict: default_branch_condition missing")
    if ref_name.get("include") != [expected_branch] or ref_name.get("exclude") != []:
        raise RuntimeError(
            "governance drift: ruleset branch condition differs from canonical target"
        )

    params = _mapping(
        _rule(rules, "required_status_checks").get("parameters"),
        label="required_status_checks.parameters",
    )
    strict = h2.get("strict_required_status_checks")
    do_not_enforce = h2.get("do_not_enforce_on_create")
    if strict is not True or do_not_enforce is not False:
        raise RuntimeError("governance policy conflict: status-check policy must remain strict")
    if params.get("strict_required_status_checks_policy") is not True:
        raise RuntimeError("governance drift: strict required status checks are disabled")
    if params.get("do_not_enforce_on_create") is not False:
        raise RuntimeError("governance drift: status checks are not enforced on branch creation")

    expected_raw = h2.get("required_checks")
    if not isinstance(expected_raw, list) or not expected_raw:
        raise RuntimeError("governance policy conflict: required_checks must not be empty")
    expected: set[tuple[str, int]] = set()
    for index, raw in enumerate(expected_raw):
        check = _mapping(raw, label=f"h2.required_checks[{index}]")
        context = check.get("context")
        integration_id = check.get("integration_id")
        if (
            not isinstance(context, str)
            or not context
            or not isinstance(integration_id, int)
            or isinstance(integration_id, bool)
            or integration_id <= 0
        ):
            raise RuntimeError("governance policy conflict: malformed required check")
        key = (context, integration_id)
        if key in expected:
            raise RuntimeError(f"governance policy conflict: duplicate required check {key!r}")
        expected.add(key)

    actual_raw = params.get("required_status_checks")
    if not isinstance(actual_raw, list):
        raise RuntimeError("governance visibility unknown: live required checks are missing")
    actual: set[tuple[str, int]] = set()
    for index, raw in enumerate(actual_raw):
        check = _mapping(raw, label=f"required_status_checks[{index}]")
        context = check.get("context")
        integration_id = check.get("integration_id")
        if not isinstance(context, str) or not isinstance(integration_id, int):
            raise RuntimeError("governance visibility unknown: malformed live required check")
        actual.add((context, integration_id))
    if actual != expected:
        raise RuntimeError(
            "governance drift: live required checks differ from canonical policy: "
            f"actual={sorted(actual)!r} expected={sorted(expected)!r}"
        )
    return {
        "strict": True,
        "do_not_enforce_on_create": False,
        "required_checks": sorted(context for context, _ in actual),
    }


def validate_solo_review_governance(
    h2: Mapping[str, object],
    detail: Mapping[str, object],
) -> dict[str, object]:
    profile = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    expected = _mapping(
        profile.get("target_pull_request_rule"),
        label="h2.solo_maintainer_profile.target_pull_request_rule",
    )
    rules = _list(detail.get("rules"), label="ruleset.rules")
    params = _mapping(
        _rule(rules, "pull_request").get("parameters"),
        label="pull_request.parameters",
    )

    if expected.get("minimum_approving_review_count") != 0:
        raise RuntimeError("solo governance policy conflict: native approval count must be zero")
    expected_fields = (
        "minimum_approving_review_count",
        "dismiss_stale_reviews_on_push",
        "require_code_owner_review",
        "require_last_push_approval",
        "required_review_thread_resolution",
        "require_extra_approval_for_unattributed_changes",
        "allowed_merge_methods",
    )
    live_field = {
        "minimum_approving_review_count": "required_approving_review_count",
        "dismiss_stale_reviews_on_push": "dismiss_stale_reviews_on_push",
        "require_code_owner_review": "require_code_owner_review",
        "require_last_push_approval": "require_last_push_approval",
        "required_review_thread_resolution": "required_review_thread_resolution",
        "require_extra_approval_for_unattributed_changes": (
            "require_extra_approval_for_unattributed_changes"
        ),
        "allowed_merge_methods": "allowed_merge_methods",
    }
    evidence: dict[str, object] = {}
    for field in expected_fields:
        expected_value = expected.get(field)
        actual_value = params.get(live_field[field])
        if field == "allowed_merge_methods":
            if expected_value != ["merge"]:
                raise RuntimeError("solo governance policy conflict: merge-only is required")
            if actual_value != ["merge"]:
                raise RuntimeError("governance drift: solo mode must remain merge-only")
        elif actual_value is not expected_value and actual_value != expected_value:
            raise RuntimeError(
                f"governance drift: solo review field {field} "
                f"actual={actual_value!r} expected={expected_value!r}"
            )
        evidence[field] = actual_value

    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    if review.get("ordinary_minimum_independent_approvals") != 0:
        raise RuntimeError("solo governance policy conflict: ordinary independent approvals must be 0")
    if review.get("critical_minimum_independent_approvals") != 0:
        raise RuntimeError("solo governance policy conflict: critical independent approvals must be 0")
    if review.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError(
            "solo governance policy conflict: independent review must be NOT_PERFORMED"
        )
    if review.get("maintainer_attestation_must_bind_current_head") is not True:
        raise RuntimeError("solo governance policy conflict: head-bound attestation is required")
    return evidence


def build_evidence(candidate_sha: str) -> dict[str, object]:
    head = legacy._git("rev-parse", "HEAD")
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")
    try:
        policy = _mapping(
            json.loads(POLICY_PATH.read_text(encoding="utf-8")),
            label="enterprise policy",
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("enterprise policy must be valid UTF-8 JSON") from exc
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    mode = h2.get("governance_mode", "independent")
    if mode not in {"independent", "solo_maintainer"}:
        raise RuntimeError(f"governance policy conflict: unsupported governance_mode {mode!r}")

    repository = h2.get("repository")
    ruleset_name = h2.get("ruleset_name")
    target = h2.get("target")
    if not all(isinstance(value, str) and value for value in (repository, ruleset_name, target)):
        raise RuntimeError("governance policy identity is incomplete")
    repository = cast(str, repository)
    ruleset_name = cast(str, ruleset_name)
    target = cast(str, target)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    repository_detail = _mapping(
        legacy._github_json(f"{legacy.API_ROOT}/{repository}", token=token),
        label="repository detail",
    )
    merge_settings_detail = legacy._resolve_repository_merge_settings(
        repository,
        repository_detail,
        token=token,
    )
    inventory = legacy._github_json(f"{legacy.API_ROOT}/{repository}/rulesets", token=token)
    rulesets = _list(inventory, label="rulesets")
    summary = legacy._find_ruleset(rulesets, name=ruleset_name, target=target)
    ruleset_id = summary.get("id")
    if not isinstance(ruleset_id, int):
        raise RuntimeError("governance visibility unknown: ruleset ID is missing")
    detail = _mapping(
        legacy._github_json(
            f"{legacy.API_ROOT}/{repository}/rulesets/{ruleset_id}",
            token=token,
        ),
        label="ruleset detail",
    )
    if detail.get("enforcement") != "active":
        raise RuntimeError("governance drift: ruleset is not active")

    bypass = legacy.validate_bypass_governance(h2, detail, ruleset_id=ruleset_id)
    candidate_commit = _mapping(
        legacy._github_json(
            f"{legacy.API_ROOT}/{repository}/commits/{candidate_sha}",
            token=token,
        ),
        label="candidate commit",
    )
    signing = legacy.validate_signed_commit_enforcement_guard(detail, candidate_commit)
    status_checks = validate_required_status_checks(h2, detail)
    if mode == "independent":
        review = legacy.validate_review_governance(policy, detail)
    else:
        review = validate_solo_review_governance(h2, detail)
    repository_merge = legacy.validate_repository_merge_settings(
        policy,
        merge_settings_detail,
    )
    return {
        "schema": "lukart.repository-governance-mode-integrity.v1",
        "candidate_sha": candidate_sha,
        "governance_mode": mode,
        "ruleset_id": ruleset_id,
        "bypass_actors": bypass,
        "signing_enforcement": signing,
        "review_rule": review,
        "required_status_checks": status_checks,
        "repository_merge_settings": repository_merge,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed mode-aware live repository governance gate"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/repository-governance-mode-integrity.json",
    )
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha)
    except RuntimeError as exc:
        print(f"REPOSITORY_GOVERNANCE_MODE_INTEGRITY=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("REPOSITORY_GOVERNANCE_MODE_INTEGRITY=PASS")
    print(f"GOVERNANCE_MODE={evidence['governance_mode']}")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
