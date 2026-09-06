from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from core.p3.contracts import require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = "config/enterprise_v1.json"
API_ROOT = "https://api.github.com/repos"


def _sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_json_digest(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(canonical)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a list")
    return cast(list[object], value)


def _required_check_bindings(
    h2_policy: Mapping[str, object],
) -> list[Mapping[str, object]]:
    raw = _list(h2_policy.get("required_checks"), label="h2.required_checks")
    bindings: list[Mapping[str, object]] = []
    for index, item in enumerate(raw):
        bindings.append(_mapping(item, label=f"h2.required_checks[{index}]"))
    if not bindings:
        raise RuntimeError("h2.required_checks must not be empty")
    return bindings


def _find_ruleset_summary(
    rulesets: list[object],
    *,
    name: str,
    target: str,
) -> Mapping[str, object]:
    for index, item in enumerate(rulesets):
        summary = _mapping(item, label=f"rulesets[{index}]")
        if summary.get("name") == name and summary.get("target") == target:
            return summary
    raise RuntimeError(
        f"repository policy drift: expected ruleset {name!r} target={target!r} is missing"
    )


def _rule_by_type(
    rules: list[object],
    *,
    rule_type: str,
) -> Mapping[str, object]:
    for index, item in enumerate(rules):
        rule = _mapping(item, label=f"rules[{index}]")
        if rule.get("type") == rule_type:
            return rule
    raise RuntimeError(f"repository policy drift: required rule type {rule_type!r} is missing")


def validate_snapshot(
    *,
    candidate_sha: str,
    head_sha: str,
    policy: Mapping[str, object],
    rulesets: list[object],
    ruleset_detail: Mapping[str, object],
    workflow_texts: Mapping[str, str],
) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(head_sha, field_name="head_sha", lengths=(40,))
    if candidate != head:
        raise RuntimeError(
            f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}"
        )

    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    repository = str(h2.get("repository", ""))
    ruleset_name = str(h2.get("ruleset_name", ""))
    target = str(h2.get("target", ""))
    enforcement = str(h2.get("enforcement", ""))
    default_branch_condition = str(h2.get("default_branch_condition", ""))
    if not repository or not ruleset_name or not target or not enforcement:
        raise RuntimeError("h2 repository policy identity is incomplete")

    summary = _find_ruleset_summary(rulesets, name=ruleset_name, target=target)
    if summary.get("enforcement") != enforcement:
        raise RuntimeError(
            "repository policy drift: ruleset enforcement mismatch: "
            f"actual={summary.get('enforcement')!r} expected={enforcement!r}"
        )
    if ruleset_detail.get("id") != summary.get("id"):
        raise RuntimeError(
            "repository policy visibility mismatch: ruleset detail ID is inconsistent"
        )
    if ruleset_detail.get("name") != ruleset_name or ruleset_detail.get("target") != target:
        raise RuntimeError(
            "repository policy visibility mismatch: ruleset detail identity is inconsistent"
        )
    if ruleset_detail.get("enforcement") != enforcement:
        raise RuntimeError("repository policy drift: detailed ruleset is not actively enforced")

    conditions = _mapping(ruleset_detail.get("conditions"), label="ruleset.conditions")
    ref_name = _mapping(conditions.get("ref_name"), label="ruleset.conditions.ref_name")
    includes = _list(ref_name.get("include"), label="ruleset.conditions.ref_name.include")
    if default_branch_condition not in includes:
        raise RuntimeError(
            "repository policy drift: ruleset does not target the canonical default branch"
        )

    expected_bypass = _list(
        h2.get("allowed_bypass_actors"),
        label="h2.allowed_bypass_actors",
    )
    actual_bypass = _list(ruleset_detail.get("bypass_actors"), label="ruleset.bypass_actors")
    if actual_bypass != expected_bypass:
        raise RuntimeError(
            "repository policy drift: undeclared bypass actors present: "
            f"actual={actual_bypass!r} expected={expected_bypass!r}"
        )
    expected_user_bypass = str(h2.get("current_user_can_bypass", ""))
    if ruleset_detail.get("current_user_can_bypass") != expected_user_bypass:
        raise RuntimeError(
            "repository policy drift: current-user bypass capability mismatch: "
            f"actual={ruleset_detail.get('current_user_can_bypass')!r} "
            f"expected={expected_user_bypass!r}"
        )

    rules = _list(ruleset_detail.get("rules"), label="ruleset.rules")
    required_rule_types = {
        str(item)
        for item in _list(h2.get("required_rule_types"), label="h2.required_rule_types")
    }
    actual_rule_types = {
        str(_mapping(item, label="ruleset.rule").get("type", "")) for item in rules
    }
    missing_rule_types = sorted(required_rule_types - actual_rule_types)
    if missing_rule_types:
        raise RuntimeError(
            f"repository policy drift: missing rule types: {missing_rule_types}"
        )

    required_status_rule = _rule_by_type(rules, rule_type="required_status_checks")
    status_params = _mapping(
        required_status_rule.get("parameters"),
        label="ruleset.required_status_checks.parameters",
    )
    expected_strict = h2.get("strict_required_status_checks")
    if status_params.get("strict_required_status_checks_policy") is not expected_strict:
        raise RuntimeError(
            "repository policy drift: strict required-status policy mismatch"
        )
    expected_on_create = h2.get("do_not_enforce_on_create")
    if status_params.get("do_not_enforce_on_create") is not expected_on_create:
        raise RuntimeError(
            "repository policy drift: do_not_enforce_on_create mismatch"
        )

    actual_checks_raw = _list(
        status_params.get("required_status_checks"),
        label="ruleset.required_status_checks",
    )
    actual_checks: set[tuple[str, int]] = set()
    for index, item in enumerate(actual_checks_raw):
        check = _mapping(item, label=f"ruleset.required_status_checks[{index}]")
        context = str(check.get("context", ""))
        integration_id = check.get("integration_id")
        if not context or not isinstance(integration_id, int):
            raise RuntimeError("repository policy visibility mismatch: malformed required check")
        actual_checks.add((context, integration_id))

    expected_checks: set[tuple[str, int]] = set()
    workflow_digests: dict[str, str] = {}
    for index, binding in enumerate(_required_check_bindings(h2)):
        context = str(binding.get("context", ""))
        integration_id = binding.get("integration_id")
        workflow = str(binding.get("workflow", ""))
        job_id = str(binding.get("job_id", ""))
        if not context or not isinstance(integration_id, int) or not workflow or not job_id:
            raise RuntimeError(f"h2.required_checks[{index}] binding is incomplete")
        if context != job_id and not context.startswith(f"{job_id} ("):
            raise RuntimeError(
                f"h2.required_checks[{index}] context {context!r} is not bound to job {job_id!r}"
            )
        workflow_text = workflow_texts.get(workflow)
        if workflow_text is None:
            raise RuntimeError(f"canonical workflow is missing: {workflow}")
        if "pull_request:" not in workflow_text:
            raise RuntimeError(
                "canonical required-check workflow lacks pull_request trigger: "
                f"{workflow}"
            )
        if f"\n  {job_id}:\n" not in workflow_text:
            raise RuntimeError(
                f"canonical required-check job identity is missing: {workflow}#{job_id}"
            )
        workflow_digests[workflow] = _sha256_text(workflow_text)
        expected_checks.add((context, integration_id))

    missing_checks = sorted(expected_checks - actual_checks)
    if missing_checks:
        rendered = [f"{context}@{integration_id}" for context, integration_id in missing_checks]
        raise RuntimeError(
            f"repository policy drift: missing required merge checks: {rendered}"
        )

    additional_checks = sorted(actual_checks - expected_checks)
    return {
        "schema": "lukart.hardcore-h2-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "repository": repository,
        "ruleset_id": summary.get("id"),
        "ruleset_name": ruleset_name,
        "ruleset_target": target,
        "ruleset_enforcement": enforcement,
        "ruleset_digest": _canonical_json_digest(ruleset_detail),
        "ruleset_inventory_digest": _canonical_json_digest(rulesets),
        "enterprise_policy_digest": _canonical_json_digest(policy),
        "required_checks": [
            {"context": context, "integration_id": integration_id}
            for context, integration_id in sorted(expected_checks)
        ],
        "additional_required_checks": [
            {"context": context, "integration_id": integration_id}
            for context, integration_id in additional_checks
        ],
        "workflow_digests": dict(sorted(workflow_digests.items())),
        "bypass_actors": actual_bypass,
        "current_user_can_bypass": ruleset_detail.get("current_user_can_bypass"),
        "policy_visibility": "CONFIRMED",
        "state": "CONTROL_PASS",
    }


def _github_json(url: str, *, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lukart-ros-hardcore-h2",
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
        raise RuntimeError(f"POLICY_VISIBILITY_UNKNOWN: cannot read {url}: {exc}") from exc


def build_h2_evidence(candidate_sha: str) -> dict[str, object]:
    head_sha = _git("rev-parse", "HEAD")
    policy = _mapping(
        json.loads((ROOT / POLICY_PATH).read_text(encoding="utf-8")),
        label="enterprise policy",
    )
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    repository = str(h2.get("repository", ""))
    ruleset_name = str(h2.get("ruleset_name", ""))
    target = str(h2.get("target", ""))
    if not repository:
        raise RuntimeError("h2 repository identity is missing")

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    rulesets_payload = _github_json(f"{API_ROOT}/{repository}/rulesets", token=token)
    rulesets = _list(rulesets_payload, label="live ruleset inventory")
    summary = _find_ruleset_summary(rulesets, name=ruleset_name, target=target)
    ruleset_id = summary.get("id")
    if not isinstance(ruleset_id, int):
        raise RuntimeError("POLICY_VISIBILITY_UNKNOWN: matching ruleset has no integer ID")
    detail_payload = _github_json(
        f"{API_ROOT}/{repository}/rulesets/{ruleset_id}",
        token=token,
    )
    ruleset_detail = _mapping(detail_payload, label="live ruleset detail")

    workflow_paths = {
        str(binding.get("workflow", "")) for binding in _required_check_bindings(h2)
    }
    if "" in workflow_paths:
        raise RuntimeError("h2 required-check workflow path is empty")
    workflow_texts = {
        path: (ROOT / path).read_text(encoding="utf-8") for path in workflow_paths
    }
    return validate_snapshot(
        candidate_sha=candidate_sha,
        head_sha=head_sha,
        policy=policy,
        rulesets=rulesets,
        ruleset_detail=ruleset_detail,
        workflow_texts=workflow_texts,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate H2 repository ruleset and required-check integrity"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/h2-repository-policy-evidence.json",
    )
    args = parser.parse_args()

    evidence = build_h2_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H2_REPOSITORY_POLICY=PASS")
    print(f"H2_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H2_RULESET_ID={evidence['ruleset_id']}")
    print(f"H2_RULESET_DIGEST={evidence['ruleset_digest']}")
    print(f"H2_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
