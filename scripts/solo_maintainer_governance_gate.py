from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

import scripts.repository_governance_transition_gate as transition

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.github.com/repos"
ATTESTATION_MARKER = "LUKART-SOLO-MAINTAINER-ATTESTATION-V1"
_GLOB_META = frozenset("*?[")
_FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


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
    return parsed.astimezone(UTC)


def validate_candidate_sha(candidate_sha: str) -> str:
    if not isinstance(candidate_sha, str) or _FULL_SHA_RE.fullmatch(candidate_sha) is None:
        raise RuntimeError("candidate SHA must be exactly 40 hexadecimal characters")
    return candidate_sha.lower()


def validate_repository_name(repository: str) -> str:
    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise RuntimeError("repository identity must be exactly owner/name")
    return repository


def build_candidate_check_runs_url(
    repository: str,
    candidate_sha: str,
    *,
    page: int,
) -> str:
    repository = validate_repository_name(repository)
    candidate_sha = validate_candidate_sha(candidate_sha)
    if not isinstance(page, int) or isinstance(page, bool) or page <= 0:
        raise RuntimeError("check-runs page must be a positive integer")
    query = urlencode({"filter": "latest", "per_page": 100, "page": page})
    return f"{API_ROOT}/{repository}/commits/{candidate_sha}/check-runs?{query}"


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


def _github_check_runs(
    repository: str,
    candidate_sha: str,
    *,
    token: str | None,
    max_pages: int = 10,
) -> list[object]:
    candidate_sha = validate_candidate_sha(candidate_sha)
    repository = validate_repository_name(repository)
    collected: list[object] = []
    for page in range(1, max_pages + 1):
        payload = _mapping(
            _github_json(
                build_candidate_check_runs_url(repository, candidate_sha, page=page),
                token=token,
            ),
            label=f"check-runs response page {page}",
        )
        runs = _list(payload.get("check_runs"), label=f"check-runs page {page}")
        for index, raw in enumerate(runs):
            check = _mapping(raw, label=f"check-runs page {page}[{index}]")
            if check.get("head_sha") != candidate_sha:
                raise RuntimeError(
                    "SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: check-run data is not bound "
                    "to the exact candidate SHA"
                )
        collected.extend(runs)
        if len(runs) < 100:
            return collected
    raise RuntimeError("SOLO_GOVERNANCE_VISIBILITY_UNKNOWN: check-runs pagination limit exceeded")


def validate_profile(profile: Mapping[str, object]) -> dict[str, object]:
    maintainer = profile.get("maintainer_id")
    default_branch = profile.get("default_branch")
    if not isinstance(maintainer, str) or not maintainer:
        raise RuntimeError("solo profile maintainer_id must be non-empty text")
    if not isinstance(default_branch, str) or not default_branch:
        raise RuntimeError("solo profile default_branch must be non-empty text")
    if profile.get("independent_external_review") != "NOT_PERFORMED":
        raise RuntimeError("solo profile must record independent_external_review=NOT_PERFORMED")
    if profile.get("reviewer_independent") is not False:
        raise RuntimeError("solo profile must record reviewer_independent=false")

    attestation = _mapping(profile.get("attestation"), label="solo.attestation")
    expected_attestation = {
        "marker": ATTESTATION_MARKER,
        "decision": "ACCEPT",
        "revocation_decision": "REVOKE",
        "must_bind_current_head": True,
        "must_follow_terminal_technical_success": True,
        "author_association": "OWNER",
    }
    if dict(attestation) != expected_attestation:
        raise RuntimeError("solo attestation contract differs from hardened contract")

    cooldowns = _mapping(profile.get("cooldown_seconds"), label="solo.cooldown_seconds")
    if dict(cooldowns) != {"ordinary": 0, "critical": 7200, "governance": 86400}:
        raise RuntimeError("solo cooldown contract differs from hardened contract")

    target = _mapping(profile.get("target_pull_request_rule"), label="solo.target_pull_request_rule")
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

    governance_paths = _string_list(profile.get("governance_paths"), label="solo.governance_paths")
    support_paths = _string_list(
        profile.get("governance_support_paths"),
        label="solo.governance_support_paths",
    )
    if not set(governance_paths).issubset(set(support_paths)):
        raise RuntimeError("all governance paths must be allowed governance support paths")

    return {
        "maintainer_id": maintainer,
        "default_branch": default_branch,
        "cooldown_seconds": dict(cooldowns),
        "governance_paths": governance_paths,
        "governance_support_paths": support_paths,
        "required_solo_check": dict(solo_check),
        "independent_external_review": "NOT_PERFORMED",
        "reviewer_independent": False,
    }


def validate_exact_critical_paths(root: Path, critical_paths: list[str]) -> list[str]:
    verified: list[str] = []
    for raw in critical_paths:
        pattern = raw.lstrip("/")
        if pattern.endswith("/**"):
            base = root / pattern[:-3].rstrip("/")
            if not base.is_dir():
                raise RuntimeError(
                    f"critical-path existence drift: subtree critical artifact {raw!r} is missing"
                )
            if not any(item.is_file() for item in base.rglob("*")):
                raise RuntimeError(
                    f"critical-path existence drift: subtree critical artifact {raw!r} has no files"
                )
        elif any(char in pattern for char in _GLOB_META):
            matches = [path for path in root.glob(pattern) if path.is_file()]
            if not matches:
                raise RuntimeError(
                    f"critical-path existence drift: glob critical artifact {raw!r} has no files"
                )
        else:
            path = root / pattern
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
    governance_changed = any(_matches_any(path, governance_paths) for path in changed_files)
    if governance_changed:
        outside = sorted(
            path for path in changed_files if not _matches_any(path, governance_support_paths)
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


def _int_or_zero(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def validate_technical_checks(
    check_runs: Sequence[object],
    *,
    required_contexts: list[str],
    self_context: str,
    candidate_sha: str,
    required_integration_ids: Mapping[str, int] | None = None,
) -> datetime:
    candidate_sha = validate_candidate_sha(candidate_sha)
    if self_context in required_contexts:
        raise RuntimeError("technical required checks must not contain solo-governance self context")
    if not required_contexts:
        raise RuntimeError("solo governance requires technical checks")
    expected = list(required_contexts)
    if len(set(expected)) != len(expected):
        raise RuntimeError("solo technical checks contain duplicate contexts")
    latest: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(check_runs):
        check = _mapping(raw, label=f"check_runs[{index}]")
        if check.get("head_sha") != candidate_sha:
            raise RuntimeError("solo technical check is not bound to the exact candidate SHA")
        name = check.get("name")
        if not isinstance(name, str) or name not in expected:
            continue
        if required_integration_ids is not None:
            expected_app_id = required_integration_ids.get(name)
            if not isinstance(expected_app_id, int):
                raise RuntimeError(f"missing canonical integration binding for {name!r}")
            app = _mapping(check.get("app"), label=f"check_runs[{index}].app")
            if app.get("id") != expected_app_id:
                raise RuntimeError(
                    f"solo technical check integration mismatch: {name!r} "
                    f"actual={app.get('id')!r} expected={expected_app_id!r}"
                )
        previous = latest.get(name)
        current_key = (str(check.get("started_at") or ""), _int_or_zero(check.get("id")))
        previous_key = (
            str(previous.get("started_at") or ""),
            _int_or_zero(previous.get("id")),
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
            _parse_time(check.get("completed_at"), label=f"check {context} completed_at")
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
    candidate_sha = validate_candidate_sha(candidate_sha)
    matching: list[tuple[datetime, int, Mapping[str, str]]] = []
    for index, raw in enumerate(comments):
        comment = _mapping(raw, label=f"comments[{index}]")
        fields = _attestation_fields(comment.get("body"))
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
            raise RuntimeError("solo attestation must not have GitHub App provenance")
        created_at_raw = comment.get("created_at")
        updated_at_raw = comment.get("updated_at")
        if not isinstance(created_at_raw, str) or not isinstance(updated_at_raw, str):
            raise RuntimeError("solo attestation timestamps are missing")
        if created_at_raw != updated_at_raw:
            raise RuntimeError("solo attestation comment was edited")
        created_at = _parse_time(created_at_raw, label=f"comments[{index}].created_at")
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool):
            raise RuntimeError("solo attestation comment id must be an integer")
        matching.append((created_at, comment_id, fields))

    if not matching:
        raise RuntimeError("solo maintainer attestation for current head is missing")

    matching.sort(key=lambda item: (item[0], item[1]))
    created_at, comment_id, fields = matching[-1]
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
    if created_at < technical_ready_at:
        raise RuntimeError("solo attestation predates terminal technical success")
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
        "reviewer_independent": False,
    }


def _technical_bindings(h2: Mapping[str, object]) -> dict[str, int]:
    rows = _list(h2.get("technical_required_checks"), label="h2.technical_required_checks")
    bindings: dict[str, int] = {}
    for index, raw in enumerate(rows):
        check = _mapping(raw, label=f"h2.technical_required_checks[{index}]")
        context = check.get("context")
        integration_id = check.get("integration_id")
        if not isinstance(context, str) or not context:
            raise RuntimeError("technical required check context must be non-empty text")
        if context == "solo-governance":
            raise RuntimeError("technical required checks must not contain solo-governance")
        if (
            not isinstance(integration_id, int)
            or isinstance(integration_id, bool)
            or integration_id <= 0
        ):
            raise RuntimeError(f"technical required check integration invalid for {context!r}")
        if context in bindings:
            raise RuntimeError("technical required checks contain duplicate context")
        bindings[context] = integration_id
    if not bindings:
        raise RuntimeError("technical required checks must not be empty")
    return bindings


def build_evidence(candidate_sha: str, *, root: Path = ROOT) -> dict[str, object]:
    candidate_sha = validate_candidate_sha(candidate_sha)
    head = _git("rev-parse", "HEAD") if root == ROOT else candidate_sha
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")

    enterprise = _load_json(root / "config" / "enterprise_v1.json", label="enterprise policy")
    h2 = _mapping(enterprise.get("h2_repository_policy"), label="h2_repository_policy")
    transition.validate_state_machine(h2)
    transition.validate_state_contract(h2)
    transition.validate_check_dependency_graph(h2)
    transition.validate_profile_truthfulness(h2)
    state = h2.get("governance_state")
    if state not in transition.STATES:
        raise RuntimeError(f"unsupported governance_state {state!r}")
    profile_raw = _mapping(h2.get("solo_maintainer_profile"), label="h2.solo_maintainer_profile")
    profile = validate_profile(profile_raw)
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    critical_paths = _string_list(review.get("critical_paths"), label="h2.review_integrity.critical_paths")
    verified_paths = validate_exact_critical_paths(root, critical_paths)

    if state == "INDEPENDENT_LOCKED":
        return {
            "schema": "lukart.solo-maintainer-governance.v1",
            "candidate_sha": candidate_sha,
            "governance_state": state,
            "mode": "DORMANT_PRE_CUTOVER",
            "profile": profile,
            "critical_paths": verified_paths,
            "independent_external_review": "NOT_PERFORMED",
            "reviewer_independent": False,
            "state": "DORMANT_PASS",
        }

    repository_raw = h2.get("repository")
    if not isinstance(repository_raw, str) or not repository_raw:
        raise RuntimeError("enterprise repository identity is missing")
    repository = validate_repository_name(repository_raw)
    default_branch = cast(str, profile["default_branch"])
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

    file_rows = _github_list(f"{API_ROOT}/{repository}/pulls/{pr_number}/files", token=token)
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
        governance_support_paths=cast(list[str], profile["governance_support_paths"]),
    )
    technical_bindings = _technical_bindings(h2)
    technical_ready_at = validate_technical_checks(
        _github_check_runs(repository, candidate_sha, token=token),
        required_contexts=list(technical_bindings),
        self_context="solo-governance",
        candidate_sha=candidate_sha,
        required_integration_ids=technical_bindings,
    )

    base_evidence: dict[str, object] = {
        "schema": "lukart.solo-maintainer-governance.v1",
        "candidate_sha": candidate_sha,
        "governance_state": state,
        "pr_number": pr_number,
        "risk_class": risk_class,
        "changed_files": sorted(changed_files),
        "technical_ready_at": technical_ready_at.isoformat(),
        "critical_paths": verified_paths,
        "independent_external_review": "NOT_PERFORMED",
        "reviewer_independent": False,
    }
    if state == "SOLO_ARMED":
        return {
            **base_evidence,
            "mode": "ARMED_READINESS",
            "attestation": "NOT_REQUIRED_UNTIL_SOLO_ACTIVE",
            "state": "ARMED_PASS",
        }

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
        **base_evidence,
        "mode": "SOLO_ACTIVE",
        "attestation": attestation,
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
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SOLO_MAINTAINER_GOVERNANCE={evidence['state']}")
    print(f"GOVERNANCE_STATE={evidence['governance_state']}")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
