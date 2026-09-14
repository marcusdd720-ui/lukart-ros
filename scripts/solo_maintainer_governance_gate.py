from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
ENTERPRISE_POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
CUTOVER_PLAN_PATH = ROOT / "config" / "solo_maintainer_cutover_v1.json"
API_ROOT = "https://api.github.com/repos"
ATTESTATION_MARKER = "LUKART-SOLO-MAINTAINER-ATTESTATION-V1"
_GLOB_META = frozenset("*?[")


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a list")
    return cast(list[object], value)


def _string_list(value: object, *, label: str) -> list[str]:
    raw = _list(value, label=label)
    if not raw or any(not isinstance(item, str) or not item for item in raw):
        raise RuntimeError(f"{label} must be a non-empty string list")
    return cast(list[str], raw)


def _load_json(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} must be valid UTF-8 JSON") from exc
    return _mapping(payload, label=label)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _parse_time(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _github_json(url: str, *, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lukart-ros-solo-governance",
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
        raise RuntimeError(
            f"SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: cannot read {url}: {exc}"
        ) from exc


def _github_list(url: str, *, token: str | None, max_pages: int = 10) -> list[object]:
    separator = "&" if "?" in url else "?"
    collected: list[object] = []
    for page in range(1, max_pages + 1):
        payload = _github_json(
            f"{url}{separator}per_page=100&page={page}",
            token=token,
        )
        items = _list(payload, label=f"GitHub list page {page}")
        collected.extend(items)
        if len(items) < 100:
            return collected
    raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: pagination limit exceeded")


def validate_profile(profile: Mapping[str, object]) -> dict[str, object]:
    maintainer = profile.get("maintainer_id")
    if not isinstance(maintainer, str) or not maintainer:
        raise RuntimeError("solo profile maintainer_id must be non-empty text")
    if profile.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError(
            "solo profile must record independent_external_review=NOT_PERFORMED"
        )

    attestation = _mapping(profile.get("attestation"), label="solo.attestation")
    if attestation.get("marker") != ATTESTATION_MARKER:
        raise RuntimeError("solo attestation marker mismatch")
    if attestation.get("decision") != "ACCEPT":
        raise RuntimeError("solo attestation ACCEPT decision is required")
    if attestation.get("revocation_decision") != "REVOKE":
        raise RuntimeError("solo attestation REVOKE decision is required")
    if attestation.get("must_bind_current_head") is not True:
        raise RuntimeError("solo attestation must bind current head")
    if attestation.get("must_follow_terminal_technical_success") is not True:
        raise RuntimeError("solo attestation must follow terminal technical success")
    if attestation.get("author_association") != "OWNER":
        raise RuntimeError("solo attestation must require OWNER association")

    cooldowns = _mapping(profile.get("cooldown_seconds"), label="solo.cooldown_seconds")
    expected_cooldowns = {"ordinary": 0, "critical": 7200, "governance": 86400}
    for risk_class, expected in expected_cooldowns.items():
        value = cooldowns.get(risk_class)
        if not isinstance(value, int) or isinstance(value, bool) or value != expected:
            raise RuntimeError(
                f"solo cooldown {risk_class} must equal {expected} seconds"
            )

    target = _mapping(
        profile.get("target_pull_request_rule"),
        label="solo.target_pull_request_rule",
    )
    expected_target = {
        "minimum_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": False,
        "require_last_push_approval": False,
        "required_review_thread_resolution": True,
        "require_extra_approval_for_unattributed_changes": False,
        "allowed_merge_methods": ["merge"],
    }
    if dict(target) != expected_target:
        raise RuntimeError("solo target pull-request rule differs from hardened contract")

    solo_check = _mapping(profile.get("required_solo_check"), label="solo.required_solo_check")
    if solo_check.get("context") != "solo-governance":
        raise RuntimeError("solo required check context must be solo-governance")
    if solo_check.get("job_id") != "solo-governance":
        raise RuntimeError("solo required check job_id must be solo-governance")
    if solo_check.get("workflow") != ".github/workflows/solo-maintainer-governance.yml":
        raise RuntimeError("solo required check workflow mismatch")
    integration_id = solo_check.get("integration_id")
    if (
        not isinstance(integration_id, int)
        or isinstance(integration_id, bool)
        or integration_id <= 0
    ):
        raise RuntimeError("solo required check integration_id must be positive")

    governance_paths = _string_list(
        profile.get("governance_paths"),
        label="solo.governance_paths",
    )
    support_paths = _string_list(
        profile.get("governance_support_paths"),
        label="solo.governance_support_paths",
    )
    if not set(governance_paths).issubset(set(support_paths)):
        raise RuntimeError("all governance paths must be allowed governance support paths")

    return {
        "maintainer_id": maintainer,
        "cooldown_seconds": dict(cooldowns),
        "governance_paths": governance_paths,
        "governance_support_paths": support_paths,
        "required_solo_check": dict(solo_check),
    }


def validate_exact_critical_paths(root: Path, critical_paths: list[str]) -> list[str]:
    verified: list[str] = []
    for raw in critical_paths:
        if any(char in raw for char in _GLOB_META):
            continue
        path = root / raw.lstrip("/")
        if not path.is_file():
            raise RuntimeError(
                f"critical-path existence drift: exact critical artifact {raw!r} is missing"
            )
        verified.append(raw)
    return sorted(verified)


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.lstrip("/")
    for raw_pattern in patterns:
        pattern = raw_pattern.lstrip("/")
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return True
        if fnmatch.fnmatchcase(normalized, pattern):
            return True
    return False


def classify_change(
    changed_files: list[str],
    *,
    critical_paths: list[str],
    governance_paths: list[str],
    governance_support_paths: list[str],
) -> str:
    if not changed_files:
        raise RuntimeError("solo governance cannot classify an empty PR")
    governance_changed = any(
        _matches_any(path, governance_paths) for path in changed_files
    )
    if governance_changed:
        outside = sorted(
            path
            for path in changed_files
            if not _matches_any(path, governance_support_paths)
        )
        if outside:
            raise RuntimeError(
                "governance topology violation: governance changes cannot be mixed with "
                f"non-governance files: {outside!r}"
            )
        return "governance"
    if any(_matches_any(path, critical_paths) for path in changed_files):
        return "critical"
    return "ordinary"


def validate_technical_checks(
    check_runs: list[object],
    *,
    required_contexts: list[str],
    self_context: str,
) -> datetime:
    expected = [context for context in required_contexts if context != self_context]
    if not expected:
        raise RuntimeError("solo governance requires independent technical checks")
    latest: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(check_runs):
        check = _mapping(raw, label=f"check_runs[{index}]")
        name = check.get("name")
        if not isinstance(name, str) or name not in expected:
            continue
        previous = latest.get(name)
        current_key = (
            str(check.get("started_at") or ""),
            int(check.get("id") or 0),
        )
        previous_key = (
            str(previous.get("started_at") or ""),
            int(previous.get("id") or 0),
        ) if previous is not None else ("", 0)
        if previous is None or current_key > previous_key:
            latest[name] = check

    missing = sorted(set(expected) - set(latest))
    if missing:
        raise RuntimeError(f"solo technical checks missing: {missing!r}")

    completed: list[datetime] = []
    for context in expected:
        check = latest[context]
        if check.get("status") != "completed" or check.get("conclusion") != "success":
            raise RuntimeError(
                f"solo technical check not terminal-success: {context!r} "
                f"status={check.get('status')!r} conclusion={check.get('conclusion')!r}"
            )
        completed.append(
            _parse_time(
                check.get("completed_at"),
                label=f"check {context} completed_at",
            )
        )
    return max(completed)


def _attestation_fields(body: object) -> Mapping[str, str] | None:
    if not isinstance(body, str):
        return None
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or lines[0] != ATTESTATION_MARKER:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def validate_attestation(
    comments: list[object],
    *,
    candidate_sha: str,
    maintainer_id: str,
    risk_class: str,
    technical_ready_at: datetime,
    cooldown_seconds: int,
) -> dict[str, object]:
    matching: list[tuple[datetime, int, Mapping[str, object], Mapping[str, str]]] = []
    for index, raw in enumerate(comments):
        comment = _mapping(raw, label=f"comments[{index}]")
        fields = _attestation_fields(comment.get("body"))
        if fields is None or fields.get("candidate_sha") != candidate_sha:
            continue
        user = _mapping(comment.get("user"), label=f"comments[{index}].user")
        if user.get("login") != maintainer_id:
            continue
        if comment.get("author_association") != "OWNER":
            continue
        created_at = _parse_time(
            comment.get("created_at"),
            label=f"comments[{index}].created_at",
        )
        comment_id = comment.get("id")
        if not isinstance(comment_id, int):
            raise RuntimeError("solo attestation comment id must be an integer")
        matching.append((created_at, comment_id, comment, fields))

    if not matching:
        raise RuntimeError("solo maintainer attestation for current head is missing")

    matching.sort(key=lambda item: (item[0], item[1]))
    created_at, comment_id, _, fields = matching[-1]
    if fields.get("decision") != "ACCEPT":
        raise RuntimeError("latest solo maintainer attestation is not ACCEPT")
    if fields.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError("solo attestation must record independent review NOT_PERFORMED")
    if fields.get("risk_class") != risk_class:
        raise RuntimeError(
            f"solo attestation risk_class mismatch: "
            f"actual={fields.get('risk_class')!r} expected={risk_class!r}"
        )

    not_before = technical_ready_at + timedelta(seconds=cooldown_seconds)
    if created_at < not_before:
        raise RuntimeError(
            "solo cooldown not satisfied: attestation precedes "
            f"{not_before.isoformat()}"
        )

    return {
        "comment_id": comment_id,
        "created_at": created_at.isoformat(),
        "risk_class": risk_class,
        "independent_external_review": "NOT_PERFORMED",
    }


def _enterprise_solo_profile(
    enterprise: Mapping[str, object],
) -> Mapping[str, object] | None:
    h2 = _mapping(enterprise.get("h2_repository_policy"), label="h2_repository_policy")
    if h2.get("governance_mode") != "solo_maintainer":
        return None
    return _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")


def build_evidence(candidate_sha: str, *, root: Path = ROOT) -> dict[str, object]:
    head = _git("rev-parse", "HEAD") if root == ROOT else candidate_sha
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")

    enterprise = _load_json(
        root / "config" / "enterprise_v1.json",
        label="enterprise policy",
    )
    h2 = _mapping(enterprise.get("h2_repository_policy"), label="h2_repository_policy")
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    critical_paths = _string_list(
        review.get("critical_paths"),
        label="h2.review_integrity.critical_paths",
    )
    exact_paths = validate_exact_critical_paths(root, critical_paths)

    active_profile = _enterprise_solo_profile(enterprise)
    if active_profile is None:
        plan = _load_json(
            root / "config" / "solo_maintainer_cutover_v1.json",
            label="solo cutover plan",
        )
        if plan.get("authoritative") is not False:
            raise RuntimeError("dormant solo cutover plan must remain non-authoritative")
        if plan.get("state") != "DORMANT_PRE_CUTOVER":
            raise RuntimeError("unexpected dormant solo cutover plan state")
        profile = validate_profile(plan)
        return {
            "schema": "lukart.solo-maintainer-governance.v1",
            "candidate_sha": candidate_sha,
            "mode": "DORMANT_PRE_CUTOVER",
            "profile": profile,
            "exact_critical_paths": exact_paths,
            "independent_external_review": "NOT_PERFORMED",
            "state": "DORMANT_PASS",
        }

    profile = validate_profile(active_profile)
    repository = h2.get("repository")
    if not isinstance(repository, str) or not repository:
        raise RuntimeError("enterprise repository identity is missing")
    default_branch = active_profile.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise RuntimeError("solo profile default_branch is missing")
    maintainer_id = cast(str, profile["maintainer_id"])
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: GitHub token is required")
    raw_pr = os.environ.get("PR_NUMBER")
    if not raw_pr or not raw_pr.isdigit() or int(raw_pr) <= 0:
        raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: PR_NUMBER is required")
    pr_number = int(raw_pr)

    pr = _mapping(
        _github_json(f"{API_ROOT}/{repository}/pulls/{pr_number}", token=token),
        label="pull request",
    )
    head_ref = _mapping(pr.get("head"), label="pull_request.head")
    base_ref = _mapping(pr.get("base"), label="pull_request.base")
    author = _mapping(pr.get("user"), label="pull_request.user")
    if pr.get("state") != "open":
        raise RuntimeError("solo governance requires an open pull request")
    if head_ref.get("sha") != candidate_sha:
        raise RuntimeError("solo governance candidate SHA does not match PR head")
    if base_ref.get("ref") != default_branch:
        raise RuntimeError("solo governance PR does not target the default branch")
    if author.get("login") != maintainer_id:
        raise RuntimeError("solo governance PR author must be the repository maintainer")

    file_rows = _github_list(
        f"{API_ROOT}/{repository}/pulls/{pr_number}/files",
        token=token,
    )
    changed_files: list[str] = []
    for index, raw in enumerate(file_rows):
        row = _mapping(raw, label=f"pull_files[{index}]")
        filename = row.get("filename")
        if not isinstance(filename, str) or not filename:
            raise RuntimeError("solo governance cannot identify a changed filename")
        changed_files.append(filename)

    risk_class = classify_change(
        changed_files,
        critical_paths=critical_paths,
        governance_paths=cast(list[str], profile["governance_paths"]),
        governance_support_paths=cast(
            list[str],
            profile["governance_support_paths"],
        ),
    )

    raw_checks = _list(h2.get("required_checks"), label="h2.required_checks")
    required_contexts: list[str] = []
    for index, raw in enumerate(raw_checks):
        check = _mapping(raw, label=f"h2.required_checks[{index}]")
        context = check.get("context")
        if not isinstance(context, str) or not context:
            raise RuntimeError("required check context must be non-empty text")
        required_contexts.append(context)
    if "solo-governance" not in required_contexts:
        raise RuntimeError("active solo governance requires solo-governance in canonical checks")

    check_payload = _mapping(
        _github_json(
            f"{API_ROOT}/{repository}/commits/{candidate_sha}/check-runs"
            "?filter=latest&per_page=100",
            token=token,
        ),
        label="check-runs response",
    )
    technical_ready_at = validate_technical_checks(
        _list(check_payload.get("check_runs"), label="check-runs"),
        required_contexts=required_contexts,
        self_context="solo-governance",
    )

    comments = _github_list(
        f"{API_ROOT}/{repository}/issues/{pr_number}/comments",
        token=token,
    )
    cooldowns = cast(dict[str, object], profile["cooldown_seconds"])
    cooldown = cooldowns.get(risk_class)
    if not isinstance(cooldown, int) or isinstance(cooldown, bool):
        raise RuntimeError("solo cooldown policy is malformed")
    attestation = validate_attestation(
        comments,
        candidate_sha=candidate_sha,
        maintainer_id=maintainer_id,
        risk_class=risk_class,
        technical_ready_at=technical_ready_at,
        cooldown_seconds=cooldown,
    )

    return {
        "schema": "lukart.solo-maintainer-governance.v1",
        "candidate_sha": candidate_sha,
        "mode": "solo_maintainer",
        "pr_number": pr_number,
        "risk_class": risk_class,
        "changed_files": sorted(changed_files),
        "technical_ready_at": technical_ready_at.isoformat(),
        "attestation": attestation,
        "exact_critical_paths": exact_paths,
        "independent_external_review": "NOT_PERFORMED",
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed solo-maintainer repository governance gate"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/solo-maintainer-governance.json",
    )
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"SOLO_MAINTAINER_GOVERNANCE=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"SOLO_MAINTAINER_GOVERNANCE={evidence['state']}")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
