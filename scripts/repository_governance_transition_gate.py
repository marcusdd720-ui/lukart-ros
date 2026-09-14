from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
CUTOVER_PATH = ROOT / "config" / "solo_maintainer_cutover_v1.json"
_FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
STATES = ("INDEPENDENT_LOCKED", "SOLO_ARMED", "SOLO_ACTIVE")
EXPECTED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "INDEPENDENT_LOCKED": ("INDEPENDENT_LOCKED", "SOLO_ARMED"),
    "SOLO_ARMED": ("SOLO_ARMED", "SOLO_ACTIVE"),
    "SOLO_ACTIVE": ("SOLO_ACTIVE",),
}
_SOLO_TARGET = {
    "minimum_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": True,
    "require_code_owner_review": False,
    "require_last_push_approval": False,
    "required_review_thread_resolution": True,
    "require_extra_approval_for_unattributed_changes": False,
    "allowed_merge_methods": ["merge"],
}


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


def _load_json_text(text: str, *, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} must be valid JSON") from exc
    return _mapping(payload, label=label)


def _load_json(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        return _load_json_text(path.read_text(encoding="utf-8"), label=label)
    except OSError as exc:
        raise RuntimeError(f"{label} is not readable") from exc


def _sha(value: str, *, label: str) -> str:
    if _FULL_SHA_RE.fullmatch(value) is None:
        raise RuntimeError(f"{label} must be exactly 40 hexadecimal characters")
    return value.lower()


def _state(h2: Mapping[str, object], *, legacy_default: bool = False) -> str:
    raw = h2.get("governance_state")
    if raw is None and legacy_default:
        return "INDEPENDENT_LOCKED"
    if raw not in STATES:
        raise RuntimeError(f"unsupported governance_state: {raw!r}")
    return cast(str, raw)


def _check_spec(raw: object, *, label: str) -> tuple[str, int, str, str]:
    check = _mapping(raw, label=label)
    context = check.get("context")
    integration_id = check.get("integration_id")
    workflow = check.get("workflow")
    job_id = check.get("job_id")
    if not isinstance(context, str) or not context:
        raise RuntimeError(f"{label}.context must be non-empty text")
    if (
        not isinstance(integration_id, int)
        or isinstance(integration_id, bool)
        or integration_id <= 0
    ):
        raise RuntimeError(f"{label}.integration_id must be a positive integer")
    if not isinstance(workflow, str) or not workflow.startswith(".github/workflows/"):
        raise RuntimeError(f"{label}.workflow must bind a repository workflow")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError(f"{label}.job_id must be non-empty text")
    return context, integration_id, workflow, job_id


def _specs(value: object, *, label: str) -> list[tuple[str, int, str, str]]:
    rows = _list(value, label=label)
    if not rows:
        raise RuntimeError(f"{label} must not be empty")
    parsed = [_check_spec(row, label=f"{label}[{index}]") for index, row in enumerate(rows)]
    contexts = [row[0] for row in parsed]
    if len(set(contexts)) != len(contexts):
        raise RuntimeError(f"{label} contains a duplicate context")
    return parsed


def validate_state_machine(h2: Mapping[str, object]) -> dict[str, object]:
    state = _state(h2)
    raw = _mapping(h2.get("governance_state_machine"), label="h2.governance_state_machine")
    actual: dict[str, tuple[str, ...]] = {}
    for source in STATES:
        destinations = _list(raw.get(source), label=f"governance_state_machine.{source}")
        if any(destination not in STATES for destination in destinations):
            raise RuntimeError(f"governance state machine has an unknown destination from {source}")
        actual[source] = tuple(cast(list[str], destinations))
    if actual != EXPECTED_TRANSITIONS:
        raise RuntimeError(
            "governance state machine drift: expected strict LOCKED -> ARMED -> ACTIVE topology"
        )
    return {"state": state, "transitions": {key: list(value) for key, value in actual.items()}}


def validate_state_contract(h2: Mapping[str, object]) -> dict[str, object]:
    state = _state(h2)
    if h2.get("allowed_bypass_actors") != []:
        raise RuntimeError("governance state contract requires an empty bypass actor list")
    pull_rule = _mapping(h2.get("pull_request_rule"), label="h2.pull_request_rule")
    if pull_rule.get("allowed_merge_methods") != ["merge"]:
        raise RuntimeError("governance state contract requires merge-only")
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    critical_paths = review.get("critical_paths")
    if not isinstance(critical_paths, list) or not critical_paths:
        raise RuntimeError("governance state contract requires critical paths")

    if state in {"INDEPENDENT_LOCKED", "SOLO_ARMED"}:
        minimum = pull_rule.get("minimum_approving_review_count")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 2:
            raise RuntimeError("independent governance states require at least two approvals")
        for field in (
            "dismiss_stale_reviews_on_push",
            "require_code_owner_review",
            "require_last_push_approval",
            "required_review_thread_resolution",
            "require_extra_approval_for_unattributed_changes",
        ):
            if pull_rule.get(field) is not True:
                raise RuntimeError(f"independent governance state requires {field}=true")
        if review.get("ordinary_minimum_independent_approvals") != minimum:
            raise RuntimeError("ordinary independent approval floor must match native approvals")
        if review.get("critical_minimum_independent_approvals") != minimum:
            raise RuntimeError("critical independent approval floor must match native approvals")
        if review.get("approvals_must_bind_current_head") is not True:
            raise RuntimeError("independent approvals must bind current head")
        return {"state": state, "review_mode": "INDEPENDENT_NATIVE", "approvals": minimum}

    profile = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    target = _mapping(profile.get("target_pull_request_rule"), label="solo.target_pull_request_rule")
    if dict(target) != _SOLO_TARGET:
        raise RuntimeError("SOLO_ACTIVE target pull-request rule differs from hardened contract")
    if dict(pull_rule) != _SOLO_TARGET:
        raise RuntimeError("SOLO_ACTIVE canonical pull-request rule must equal the solo target")
    if review.get("ordinary_minimum_independent_approvals") != 0:
        raise RuntimeError("SOLO_ACTIVE ordinary independent approvals must be zero")
    if review.get("critical_minimum_independent_approvals") != 0:
        raise RuntimeError("SOLO_ACTIVE critical independent approvals must be zero")
    if review.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError("SOLO_ACTIVE must record independent_external_review=NOT_PERFORMED")
    if review.get("reviewer_independent") is not False:
        raise RuntimeError("SOLO_ACTIVE must record reviewer_independent=false")
    if review.get("maintainer_attestation_must_bind_current_head") is not True:
        raise RuntimeError("SOLO_ACTIVE requires head-bound maintainer attestation")
    return {"state": state, "review_mode": "SOLO_COMPENSATING_CONTROLS", "approvals": 0}


def _cycle_check(dependencies: Mapping[str, tuple[str, ...]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise RuntimeError(f"required-check dependency cycle detected at {node!r}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in dependencies[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in dependencies:
        visit(node)


def validate_check_dependency_graph(h2: Mapping[str, object]) -> dict[str, object]:
    technical = _specs(h2.get("technical_required_checks"), label="h2.technical_required_checks")
    final = _specs(h2.get("final_required_checks"), label="h2.final_required_checks")
    effective = _specs(h2.get("required_checks"), label="h2.required_checks")
    profile = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    solo_spec = _check_spec(profile.get("required_solo_check"), label="solo.required_solo_check")

    technical_contexts = [spec[0] for spec in technical]
    if solo_spec[0] in technical_contexts:
        raise RuntimeError("solo-governance must not depend on itself through technical checks")
    if final != [*technical, solo_spec]:
        raise RuntimeError("FINAL_REQUIRED_CHECKS must equal technical checks plus solo-governance")

    state = _state(h2)
    expected_effective = technical if state == "INDEPENDENT_LOCKED" else final
    if effective != expected_effective:
        raise RuntimeError(f"effective required_checks do not match governance_state {state}")

    raw_dependencies = _mapping(h2.get("check_dependencies"), label="h2.check_dependencies")
    final_contexts = [spec[0] for spec in final]
    if set(raw_dependencies) != set(final_contexts):
        raise RuntimeError("check dependency graph must define every final required context exactly once")
    dependencies: dict[str, tuple[str, ...]] = {}
    for context in final_contexts:
        raw_items = _list(raw_dependencies.get(context), label=f"check_dependencies.{context}")
        if any(not isinstance(item, str) or not item for item in raw_items):
            raise RuntimeError(f"check_dependencies.{context} must contain context names")
        items = tuple(cast(list[str], raw_items))
        if len(set(items)) != len(items):
            raise RuntimeError(f"duplicate dependency for context {context!r}")
        if context in items:
            raise RuntimeError(f"self dependency is forbidden for context {context!r}")
        unknown = sorted(set(items) - set(final_contexts))
        if unknown:
            raise RuntimeError(f"unknown check dependencies for {context!r}: {unknown!r}")
        dependencies[context] = items

    expected_technical = tuple(technical_contexts)
    if dependencies[solo_spec[0]] != expected_technical:
        raise RuntimeError("solo-governance must depend on all and only technical required checks")
    for context in technical_contexts:
        if dependencies[context]:
            raise RuntimeError(f"technical check {context!r} must not wait on final/self contexts")
    _cycle_check(dependencies)
    return {
        "state": state,
        "technical_required_checks": technical_contexts,
        "final_required_checks": final_contexts,
        "solo_context": solo_spec[0],
    }


def validate_profile_truthfulness(h2: Mapping[str, object]) -> dict[str, object]:
    profile = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    maintainer = profile.get("maintainer_id")
    default_branch = profile.get("default_branch")
    if not isinstance(maintainer, str) or not maintainer:
        raise RuntimeError("solo profile maintainer_id must be non-empty text")
    if not isinstance(default_branch, str) or not default_branch:
        raise RuntimeError("solo profile default_branch must be non-empty text")
    if profile.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError("solo profile must state independent_external_review=NOT_PERFORMED")
    if profile.get("reviewer_independent") is not False:
        raise RuntimeError("solo profile must state reviewer_independent=false")
    attestation = _mapping(profile.get("attestation"), label="solo.attestation")
    expected_attestation = {
        "marker": "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
        "decision": "ACCEPT",
        "revocation_decision": "REVOKE",
        "must_bind_current_head": True,
        "must_follow_terminal_technical_success": True,
        "author_association": "OWNER",
    }
    if dict(attestation) != expected_attestation:
        raise RuntimeError("solo maintainer attestation contract differs from hardened contract")
    cooldowns = _mapping(profile.get("cooldown_seconds"), label="solo.cooldown_seconds")
    if dict(cooldowns) != {"ordinary": 0, "critical": 7200, "governance": 86400}:
        raise RuntimeError("solo maintainer cooldown contract differs from hardened contract")
    target = _mapping(profile.get("target_pull_request_rule"), label="solo.target_pull_request_rule")
    if dict(target) != _SOLO_TARGET:
        raise RuntimeError("solo target pull-request rule differs from hardened contract")
    return {
        "maintainer_id": maintainer,
        "default_branch": default_branch,
        "independent_external_review": "NOT_PERFORMED",
        "reviewer_independent": False,
    }


def validate_transition(previous_h2: Mapping[str, object], current_h2: Mapping[str, object]) -> dict[str, str]:
    previous = _state(previous_h2, legacy_default=True)
    current = _state(current_h2)
    if current not in EXPECTED_TRANSITIONS[previous]:
        raise RuntimeError(f"forbidden governance transition: {previous} -> {current}")
    return {"previous_state": previous, "current_state": current}


def validate_legacy_cutover_is_non_authoritative(root: Path = ROOT) -> dict[str, object]:
    path = root / "config" / "solo_maintainer_cutover_v1.json"
    if not path.is_file():
        return {"present": False, "authoritative": False}
    payload = _load_json(path, label="legacy solo cutover plan")
    if payload.get("authoritative") is not False:
        raise RuntimeError("legacy solo cutover plan must remain non-authoritative")
    return {"present": True, "authoritative": False}


def build_evidence(candidate_sha: str, base_sha: str) -> dict[str, object]:
    candidate_sha = _sha(candidate_sha, label="candidate SHA")
    base_sha = _sha(base_sha, label="base SHA")
    head = _git("rev-parse", "HEAD")
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")
    parent_fields = _git("rev-list", "--parents", "-n", "1", candidate_sha).split()
    parents = parent_fields[1:]
    if base_sha not in parents:
        raise RuntimeError("transition base SHA must be a direct parent of the candidate")

    current = _load_json(POLICY_PATH, label="enterprise policy")
    current_h2 = _mapping(current.get("h2_repository_policy"), label="h2_repository_policy")
    try:
        previous_text = _git("show", f"{base_sha}:config/enterprise_v1.json")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("cannot read base enterprise policy for transition validation") from exc
    previous = _load_json_text(previous_text, label="base enterprise policy")
    previous_h2 = _mapping(previous.get("h2_repository_policy"), label="base.h2_repository_policy")

    state_machine = validate_state_machine(current_h2)
    state_contract = validate_state_contract(current_h2)
    check_graph = validate_check_dependency_graph(current_h2)
    transition = validate_transition(previous_h2, current_h2)
    profile = validate_profile_truthfulness(current_h2)
    legacy = validate_legacy_cutover_is_non_authoritative(ROOT)
    return {
        "schema": "lukart.repository-governance-transition.v1",
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "state_machine": state_machine,
        "state_contract": state_contract,
        "check_graph": check_graph,
        "transition": transition,
        "solo_profile_truthfulness": profile,
        "legacy_cutover": legacy,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical repository governance transition gate")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/repository-governance-transition.json",
    )
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha, args.base_sha)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"REPOSITORY_GOVERNANCE_TRANSITION=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPOSITORY_GOVERNANCE_TRANSITION=PASS")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"BASE_SHA={evidence['base_sha']}")
    print(f"GOVERNANCE_STATE={evidence['transition']['current_state']}")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
