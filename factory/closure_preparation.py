"""GOV-AUTO-01 deterministic closure-PR preparation from live GitHub evidence.

The module prepares a closure pull request only. It never merges, marks a stage closed,
publishes a release, or changes Product/CCL/Gold authority. GitHub live state remains the
source of truth; the existing GOV-01 verifier remains the governance consistency authority.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import time
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from core.governance_closure_v1 import (
    REQUIRED_PR_WORKFLOWS_V1,
    GovernanceClosureRecordV1,
    GovernanceLiveSnapshotV1,
    WorkflowEvidenceV1,
    WorkflowOutcome,
    verify_governance_closure_v1,
)
from factory.github_actions_client import GitHubActionsClient

TARGET_SCHEMA_V1 = "lukart.closure-preparation-target.v1"
EVIDENCE_SCHEMA_V1 = "lukart.closure-preparation-evidence.v1"
TARGET_PATH = "config/closure_preparation_target.json"
BASE_BRANCH = "main"
DEFAULT_POLL_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 900

REQUIRED_POST_MERGE_WORKFLOWS_V1 = (
    "Architectural Audit 1.0",
    "CI Foundation",
    "Enterprise CodeQL",
    "Enterprise Hardcore Gate",
    "GitHub App Smoke Test",
    "MVROS v1 Release",
    "Production Validation Program",
    "Stage Gate",
    "Stage Orchestrator",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STAGE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")


class ClosurePreparationError(RuntimeError):
    """Fail-closed closure preparation violation."""


def _require_sha(value: str, field: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise ClosurePreparationError(f"{field} must be a lowercase 40-character Git SHA")
    return value


def _require_stage(value: str, field: str) -> str:
    if not _STAGE_RE.fullmatch(value):
        raise ClosurePreparationError(f"{field} must be a canonical stage identifier")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _slug(stage_id: str) -> str:
    return stage_id.lower()


@dataclass(frozen=True, slots=True)
class ClosurePreparationTargetV1:
    stage_id: str
    next_stage_id: str
    implementation_pr: int
    architecture_doc: str
    enabled: bool = True
    schema: str = TARGET_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != TARGET_SCHEMA_V1:
            raise ClosurePreparationError(f"unsupported target schema: {self.schema}")
        _require_stage(self.stage_id, "stage_id")
        _require_stage(self.next_stage_id, "next_stage_id")
        if self.stage_id == self.next_stage_id:
            raise ClosurePreparationError("next_stage_id must differ from stage_id")
        if self.implementation_pr < 1:
            raise ClosurePreparationError("implementation_pr must be positive")
        if not self.architecture_doc.startswith("docs/"):
            raise ClosurePreparationError("architecture_doc must be under docs/")
        if not self.architecture_doc.endswith(".md"):
            raise ClosurePreparationError("architecture_doc must be a Markdown file")
        if ".." in Path(self.architecture_doc).parts:
            raise ClosurePreparationError("architecture_doc path traversal is forbidden")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "enabled": self.enabled,
            "stage_id": self.stage_id,
            "next_stage_id": self.next_stage_id,
            "implementation_pr": self.implementation_pr,
            "architecture_doc": self.architecture_doc,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> ClosurePreparationTargetV1:
        expected = {
            "schema",
            "enabled",
            "stage_id",
            "next_stage_id",
            "implementation_pr",
            "architecture_doc",
        }
        if set(raw) != expected:
            raise ClosurePreparationError("closure target contains unknown or missing fields")
        schema = raw["schema"]
        enabled = raw["enabled"]
        stage_id = raw["stage_id"]
        next_stage_id = raw["next_stage_id"]
        implementation_pr = raw["implementation_pr"]
        architecture_doc = raw["architecture_doc"]
        if not isinstance(schema, str):
            raise ClosurePreparationError("target schema must be text")
        if not isinstance(enabled, bool):
            raise ClosurePreparationError("target enabled must be boolean")
        if not isinstance(stage_id, str) or not isinstance(next_stage_id, str):
            raise ClosurePreparationError("target stage identifiers must be text")
        if not isinstance(implementation_pr, int) or isinstance(implementation_pr, bool):
            raise ClosurePreparationError("target implementation_pr must be integer")
        if not isinstance(architecture_doc, str):
            raise ClosurePreparationError("target architecture_doc must be text")
        return cls(
            schema=schema,
            enabled=enabled,
            stage_id=stage_id,
            next_stage_id=next_stage_id,
            implementation_pr=implementation_pr,
            architecture_doc=architecture_doc,
        )


@dataclass(frozen=True, slots=True)
class WorkflowRunEvidenceV1:
    run_id: int
    name: str
    event: str
    status: str
    conclusion: str
    head_sha: str

    def __post_init__(self) -> None:
        if self.run_id < 1:
            raise ClosurePreparationError("workflow run_id must be positive")
        if not self.name.strip():
            raise ClosurePreparationError("workflow name must be nonblank")
        if self.status != "completed":
            raise ClosurePreparationError(f"workflow {self.name} is not completed")
        if self.conclusion != "success":
            raise ClosurePreparationError(
                f"workflow {self.name} is not success: {self.conclusion}"
            )
        _require_sha(self.head_sha, "workflow.head_sha")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "event": self.event,
            "status": self.status,
            "conclusion": self.conclusion,
            "head_sha": self.head_sha,
        }


@dataclass(frozen=True, slots=True)
class ClosurePreparationEvidenceV1:
    stage_id: str
    next_stage_id: str
    implementation_pr: int
    validated_head_sha: str
    implementation_merge_sha: str
    merge_parent_shas: tuple[str, ...]
    pr_workflows: tuple[WorkflowRunEvidenceV1, ...]
    post_merge_workflows: tuple[WorkflowRunEvidenceV1, ...]
    baseline_tag_object_sha: str
    baseline_target_commit_sha: str
    latest_release_tag: str
    governance_live_snapshot_identity: str
    governance_report_identity: str
    schema: str = EVIDENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_SCHEMA_V1:
            raise ClosurePreparationError(f"unsupported evidence schema: {self.schema}")
        _require_stage(self.stage_id, "stage_id")
        _require_stage(self.next_stage_id, "next_stage_id")
        if self.implementation_pr < 1:
            raise ClosurePreparationError("implementation_pr must be positive")
        _require_sha(self.validated_head_sha, "validated_head_sha")
        _require_sha(self.implementation_merge_sha, "implementation_merge_sha")
        for sha in self.merge_parent_shas:
            _require_sha(sha, "merge_parent_sha")
        _require_sha(self.baseline_tag_object_sha, "baseline_tag_object_sha")
        _require_sha(self.baseline_target_commit_sha, "baseline_target_commit_sha")
        for digest in (
            self.governance_live_snapshot_identity,
            self.governance_report_identity,
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ClosurePreparationError("governance identities must be sha256 hex")
        if not self.latest_release_tag.strip():
            raise ClosurePreparationError("latest_release_tag must be nonblank")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "stage_id": self.stage_id,
            "next_stage_id": self.next_stage_id,
            "implementation_pr": self.implementation_pr,
            "validated_head_sha": self.validated_head_sha,
            "implementation_merge_sha": self.implementation_merge_sha,
            "merge_parent_shas": list(self.merge_parent_shas),
            "pr_workflows": [item.canonical_dict() for item in self.pr_workflows],
            "post_merge_workflows": [
                item.canonical_dict() for item in self.post_merge_workflows
            ],
            "baseline_tag_object_sha": self.baseline_tag_object_sha,
            "baseline_target_commit_sha": self.baseline_target_commit_sha,
            "latest_release_tag": self.latest_release_tag,
            "governance_live_snapshot_identity": self.governance_live_snapshot_identity,
            "governance_report_identity": self.governance_report_identity,
            "authority": "closure-preparation-only",
            "result": "PREPARED_NOT_CLOSED",
        }

    @property
    def evidence_identity(self) -> str:
        return _sha256(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        body = self.canonical_body()
        return {**body, "evidence_identity": self.evidence_identity}


@dataclass(frozen=True, slots=True)
class PreparedClosurePullRequestV1:
    number: int
    html_url: str
    branch: str
    evidence_path: str
    evidence_identity: str


class ClosureGitHubPort(Protocol):
    repository: str

    def get_pull_request(self, number: int) -> dict[str, Any]: ...
    def get_commit(self, sha: str) -> dict[str, Any]: ...
    def get_ref(self, ref: str) -> dict[str, Any]: ...
    def get_tag_object(self, sha: str) -> dict[str, Any]: ...
    def get_latest_release(self) -> dict[str, Any]: ...
    def list_runs_for_sha(self, sha: str, *, event: str | None = None) -> list[dict[str, Any]]: ...
    def create_branch(self, branch: str, sha: str) -> None: ...
    def create_text_file(self, *, branch: str, path: str, content: str, message: str) -> None: ...
    def update_text_file(
        self,
        *,
        branch: str,
        path: str,
        content: str,
        current_sha: str,
        message: str,
    ) -> None: ...
    def get_text_file(self, *, ref: str, path: str) -> tuple[str, str]: ...
    def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> dict[str, Any]: ...


class ClosurePreparationGitHubClient(GitHubActionsClient):
    """Narrow GitHub capability adapter used only for closure preparation."""

    @classmethod
    def from_environment(cls) -> ClosurePreparationGitHubClient:
        return cast(ClosurePreparationGitHubClient, super().from_environment())

    def get_pull_request(self, number: int) -> dict[str, Any]:
        return self._api("GET", f"/repos/{self.repository}/pulls/{number}")

    def get_commit(self, sha: str) -> dict[str, Any]:
        return self._api("GET", f"/repos/{self.repository}/commits/{sha}")

    def get_ref(self, ref: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(ref, safe="/")
        return self._api("GET", f"/repos/{self.repository}/git/ref/{encoded}")

    def get_tag_object(self, sha: str) -> dict[str, Any]:
        return self._api("GET", f"/repos/{self.repository}/git/tags/{sha}")

    def get_latest_release(self) -> dict[str, Any]:
        return self._api("GET", f"/repos/{self.repository}/releases/latest")

    def list_runs_for_sha(
        self, sha: str, *, event: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, str | int] = {"head_sha": sha, "per_page": 100}
        if event is not None:
            query["event"] = event
        data = self._api(
            "GET",
            f"/repos/{self.repository}/actions/runs?{urllib.parse.urlencode(query)}",
        )
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise ClosurePreparationError("GitHub returned invalid workflow_runs")
        return [run for run in runs if isinstance(run, dict)]

    def create_branch(self, branch: str, sha: str) -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/git/refs",
            body={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    def create_text_file(
        self, *, branch: str, path: str, content: str, message: str
    ) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        quoted_path = urllib.parse.quote(path, safe="/")
        self._api(
            "PUT",
            f"/repos/{self.repository}/contents/{quoted_path}",
            body={"message": message, "content": encoded, "branch": branch},
        )

    def update_text_file(
        self,
        *,
        branch: str,
        path: str,
        content: str,
        current_sha: str,
        message: str,
    ) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        quoted_path = urllib.parse.quote(path, safe="/")
        self._api(
            "PUT",
            f"/repos/{self.repository}/contents/{quoted_path}",
            body={
                "message": message,
                "content": encoded,
                "branch": branch,
                "sha": current_sha,
            },
        )

    def get_text_file(self, *, ref: str, path: str) -> tuple[str, str]:
        quoted_path = urllib.parse.quote(path, safe="/")
        query = urllib.parse.urlencode({"ref": ref})
        data = self._api(
            "GET",
            f"/repos/{self.repository}/contents/{quoted_path}?{query}",
        )
        blob_sha = data.get("sha")
        encoded = data.get("content")
        encoding = data.get("encoding")
        if not isinstance(blob_sha, str) or not _SHA_RE.fullmatch(blob_sha):
            raise ClosurePreparationError("GitHub returned invalid file blob SHA")
        if encoding != "base64" or not isinstance(encoded, str):
            raise ClosurePreparationError("GitHub returned invalid text file encoding")
        try:
            content = base64.b64decode(encoded, validate=False).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ClosurePreparationError("GitHub returned invalid UTF-8 file content") from exc
        return content, blob_sha

    def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> dict[str, Any]:
        pull_request_token = os.environ.get("LUKART_ROS_CLOSURE_PR_TOKEN", "").strip()
        if not pull_request_token:
            raise ClosurePreparationError("scoped closure PR token is unavailable")
        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": False,
                "maintainer_can_modify": True,
            }
        ).encode("utf-8")
        return self._request(
            "POST",
            f"{self.api_base}/repos/{self.repository}/pulls",
            token=pull_request_token,
            body=payload,
        )


def load_target(path: Path = Path(TARGET_PATH)) -> ClosurePreparationTargetV1:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosurePreparationError(f"cannot load closure target: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClosurePreparationError("closure target must be a JSON object")
    return ClosurePreparationTargetV1.from_dict(raw)


def _load_baseline(path: Path = Path("pyproject.toml")) -> tuple[str, str]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        enterprise = data["tool"]["lukart"]["enterprise"]
        version = enterprise["immutable_baseline_version"]
        commit = enterprise["immutable_baseline_commit"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ClosurePreparationError(f"cannot load immutable baseline: {exc}") from exc
    if not isinstance(version, str) or not version.strip():
        raise ClosurePreparationError("immutable baseline version is invalid")
    if not isinstance(commit, str):
        raise ClosurePreparationError("immutable baseline commit is invalid")
    _require_sha(commit, "immutable_baseline_commit")
    return f"v{version}", commit


def _workflow_run(raw: dict[str, Any], expected_sha: str) -> WorkflowRunEvidenceV1:
    run_id = raw.get("id")
    name = raw.get("name")
    event = raw.get("event")
    status = raw.get("status")
    conclusion = raw.get("conclusion")
    head_sha = raw.get("head_sha")
    if not isinstance(run_id, int):
        raise ClosurePreparationError("workflow run id is invalid")
    if not isinstance(name, str):
        raise ClosurePreparationError(f"workflow run {run_id} name is invalid")
    if not isinstance(event, str):
        raise ClosurePreparationError(f"workflow run {run_id} event is invalid")
    if not isinstance(status, str):
        raise ClosurePreparationError(f"workflow run {run_id} status is invalid")
    if not isinstance(conclusion, str):
        raise ClosurePreparationError(f"workflow run {run_id} conclusion is invalid")
    if not isinstance(head_sha, str):
        raise ClosurePreparationError(f"workflow run {run_id} head SHA is invalid")
    if head_sha != expected_sha:
        raise ClosurePreparationError(f"workflow run {run_id} head SHA mismatch")
    return WorkflowRunEvidenceV1(
        run_id=run_id,
        name=name,
        event=event,
        status=status,
        conclusion=conclusion,
        head_sha=head_sha,
    )


def _validated_runs(
    raw_runs: list[dict[str, Any]],
    *,
    expected_sha: str,
    excluded_run_id: int | None = None,
) -> tuple[WorkflowRunEvidenceV1, ...]:
    filtered = [
        run
        for run in raw_runs
        if excluded_run_id is None or run.get("id") != excluded_run_id
    ]
    evidence = tuple(
        sorted(
            (_workflow_run(run, expected_sha) for run in filtered),
            key=lambda item: (item.name, item.run_id),
        )
    )
    names = [item.name for item in evidence]
    if len(names) != len(set(names)):
        raise ClosurePreparationError("workflow evidence contains duplicate workflow names")
    return evidence


def _require_workflow_names(
    runs: tuple[WorkflowRunEvidenceV1, ...],
    required_names: tuple[str, ...],
    scope: str,
) -> None:
    observed = {item.name for item in runs}
    missing = sorted(set(required_names) - observed)
    if missing:
        raise ClosurePreparationError(
            f"{scope} is missing required workflows: {', '.join(missing)}"
        )


def _extract_merge_parents(commit: dict[str, Any]) -> tuple[str, ...]:
    raw_parents = commit.get("parents")
    if not isinstance(raw_parents, list):
        raise ClosurePreparationError("merge commit parents are unavailable")
    parents: list[str] = []
    for raw in raw_parents:
        if not isinstance(raw, dict) or not isinstance(raw.get("sha"), str):
            raise ClosurePreparationError("merge commit parent identity is invalid")
        parents.append(_require_sha(str(raw["sha"]), "merge_parent_sha"))
    if len(parents) < 2:
        raise ClosurePreparationError("implementation merge must have at least two parents")
    return tuple(parents)


def _current_main_sha(client: ClosureGitHubPort) -> str:
    data = client.get_ref(f"heads/{BASE_BRANCH}")
    obj = data.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str):
        raise ClosurePreparationError("GitHub returned invalid main ref")
    return _require_sha(str(obj["sha"]), "main_sha")


def _baseline_identity(
    client: ClosureGitHubPort, baseline_tag: str, expected_target: str
) -> tuple[str, str, str]:
    ref = client.get_ref(f"tags/{baseline_tag}")
    obj = ref.get("object")
    if not isinstance(obj, dict):
        raise ClosurePreparationError("baseline tag ref is invalid")
    tag_object_sha = obj.get("sha")
    tag_object_type = obj.get("type")
    if tag_object_type != "tag" or not isinstance(tag_object_sha, str):
        raise ClosurePreparationError("baseline must remain an annotated tag")
    _require_sha(tag_object_sha, "baseline_tag_object_sha")

    tag = client.get_tag_object(tag_object_sha)
    target = tag.get("object")
    if not isinstance(target, dict) or target.get("type") != "commit":
        raise ClosurePreparationError("baseline annotated tag target is invalid")
    target_sha = target.get("sha")
    if not isinstance(target_sha, str):
        raise ClosurePreparationError("baseline target commit is invalid")
    _require_sha(target_sha, "baseline_target_commit_sha")
    if target_sha != expected_target:
        raise ClosurePreparationError("immutable baseline target drift detected")

    latest = client.get_latest_release()
    latest_tag = latest.get("tag_name")
    if not isinstance(latest_tag, str) or latest_tag != baseline_tag:
        raise ClosurePreparationError("latest release drift detected")
    return tag_object_sha, target_sha, latest_tag


def collect_closure_evidence(
    *,
    client: ClosureGitHubPort,
    target: ClosurePreparationTargetV1,
    expected_merge_sha: str,
    current_run_id: int | None,
    baseline_tag: str,
    baseline_target_commit: str,
) -> ClosurePreparationEvidenceV1:
    expected_merge_sha = _require_sha(expected_merge_sha, "expected_merge_sha")
    if not target.enabled:
        raise ClosurePreparationError("closure preparation target is disabled")

    if _current_main_sha(client) != expected_merge_sha:
        raise ClosurePreparationError("live main drifted from expected implementation merge")

    pr = client.get_pull_request(target.implementation_pr)
    if pr.get("merged") is not True:
        raise ClosurePreparationError("implementation PR is not merged")
    if pr.get("merge_commit_sha") != expected_merge_sha:
        raise ClosurePreparationError("implementation PR merge SHA mismatch")
    head = pr.get("head")
    if not isinstance(head, dict) or not isinstance(head.get("sha"), str):
        raise ClosurePreparationError("implementation PR head SHA is unavailable")
    validated_head_sha = _require_sha(str(head["sha"]), "validated_head_sha")

    commit = client.get_commit(expected_merge_sha)
    merge_parent_shas = _extract_merge_parents(commit)
    if validated_head_sha not in merge_parent_shas:
        raise ClosurePreparationError("validated PR head is not a merge parent")

    pr_runs = _validated_runs(
        client.list_runs_for_sha(validated_head_sha, event="pull_request"),
        expected_sha=validated_head_sha,
    )
    _require_workflow_names(pr_runs, REQUIRED_PR_WORKFLOWS_V1, "PR exact-head evidence")

    post_merge_runs = _validated_runs(
        client.list_runs_for_sha(expected_merge_sha),
        expected_sha=expected_merge_sha,
        excluded_run_id=current_run_id,
    )
    _require_workflow_names(
        post_merge_runs,
        REQUIRED_POST_MERGE_WORKFLOWS_V1,
        "post-merge evidence",
    )

    tag_object_sha, target_commit_sha, latest_release_tag = _baseline_identity(
        client, baseline_tag, baseline_target_commit
    )

    pr_by_name = {item.name: item for item in pr_runs}
    live = GovernanceLiveSnapshotV1(
        stage_id=target.stage_id,
        implementation_pr=target.implementation_pr,
        validated_head_sha=validated_head_sha,
        merge_sha=expected_merge_sha,
        merge_parent_shas=merge_parent_shas,
        pr_workflows=tuple(
            WorkflowEvidenceV1(
                name=name,
                outcome=WorkflowOutcome.SUCCESS,
            )
            for name in REQUIRED_PR_WORKFLOWS_V1
            if name in pr_by_name
        ),
        post_merge_success_count=len(post_merge_runs),
        post_merge_non_success_count=0,
        baseline_tag_object_sha=tag_object_sha,
        baseline_target_commit_sha=target_commit_sha,
    )
    closure = GovernanceClosureRecordV1(
        stage_id=target.stage_id,
        implementation_pr=target.implementation_pr,
        validated_head_sha=validated_head_sha,
        merge_sha=expected_merge_sha,
        baseline_tag_object_sha=tag_object_sha,
        baseline_target_commit_sha=target_commit_sha,
        next_stage_id=target.next_stage_id,
    )
    report = verify_governance_closure_v1(closure=closure, live=live)

    return ClosurePreparationEvidenceV1(
        stage_id=target.stage_id,
        next_stage_id=target.next_stage_id,
        implementation_pr=target.implementation_pr,
        validated_head_sha=validated_head_sha,
        implementation_merge_sha=expected_merge_sha,
        merge_parent_shas=merge_parent_shas,
        pr_workflows=pr_runs,
        post_merge_workflows=post_merge_runs,
        baseline_tag_object_sha=tag_object_sha,
        baseline_target_commit_sha=target_commit_sha,
        latest_release_tag=latest_release_tag,
        governance_live_snapshot_identity=live.identity,
        governance_report_identity=report.report_identity,
    )


def wait_for_closure_evidence(
    *,
    client: ClosureGitHubPort,
    target: ClosurePreparationTargetV1,
    expected_merge_sha: str,
    current_run_id: int | None,
    baseline_tag: str,
    baseline_target_commit: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
) -> ClosurePreparationEvidenceV1:
    if timeout_seconds < 1 or poll_seconds < 1:
        raise ClosurePreparationError("poll and timeout values must be positive")
    deadline = time.monotonic() + timeout_seconds
    last_error: ClosurePreparationError | None = None
    while time.monotonic() < deadline:
        try:
            return collect_closure_evidence(
                client=client,
                target=target,
                expected_merge_sha=expected_merge_sha,
                current_run_id=current_run_id,
                baseline_tag=baseline_tag,
                baseline_target_commit=baseline_target_commit,
            )
        except ClosurePreparationError as exc:
            text = str(exc)
            terminal_failure = (
                "is not success:" in text
                or "drift" in text
                or "not merged" in text
                or "mismatch" in text
                or "not a merge parent" in text
            )
            if terminal_failure:
                raise
            last_error = exc
            time.sleep(poll_seconds)
    raise ClosurePreparationError(
        f"closure evidence did not become ready: {last_error}"
    )


def render_evidence_json(evidence: ClosurePreparationEvidenceV1) -> str:
    return json.dumps(evidence.canonical_dict(), indent=2, sort_keys=True) + "\n"


def render_disabled_target(target: ClosurePreparationTargetV1) -> str:
    disabled = ClosurePreparationTargetV1(
        stage_id=target.stage_id,
        next_stage_id=target.next_stage_id,
        implementation_pr=target.implementation_pr,
        architecture_doc=target.architecture_doc,
        enabled=False,
    )
    return json.dumps(disabled.canonical_dict(), indent=2, sort_keys=True) + "\n"


def render_pr_body(
    *,
    target: ClosurePreparationTargetV1,
    evidence: ClosurePreparationEvidenceV1,
    evidence_path: str,
    preparation_run_id: int,
) -> str:
    return (
        "## PREPARED / NOT CLOSED\n\n"
        "This PR was created automatically from live GitHub evidence. It is preparation only; "
        "it does **not** certify or close the stage.\n\n"
        f"- stage: `{target.stage_id}`\n"
        f"- implementation PR: `#{target.implementation_pr}`\n"
        f"- validated implementation head: `{evidence.validated_head_sha}`\n"
        f"- implementation merge: `{evidence.implementation_merge_sha}`\n"
        f"- next approved stage: `{target.next_stage_id}`\n"
        f"- evidence: `{evidence_path}`\n"
        f"- evidence identity: `{evidence.evidence_identity}`\n"
        f"- architecture contract: `{target.architecture_doc}`\n"
        f"- preparation workflow run: `{preparation_run_id}`\n\n"
        "### Mandatory before closure\n\n"
        "1. Update the canonical architecture/roadmap/Master Plan closure record from this "
        "evidence without changing its observed identities.\n"
        "2. Validate the complete closure PR on one unchanged exact head SHA.\n"
        "3. Verify head/base drift again immediately before merge.\n"
        "4. Use guarded exact-head merge.\n"
        "5. Validate the resulting `main`, release/baseline side effects, and only then claim "
        "`CLOSED / ENGINEERING PASS`.\n\n"
        "The automation has no merge, release, Product, CCL, Gold, certification, or "
        "independent-review authority.\n"
    )


def prepare_closure_pr(
    *,
    client: ClosureGitHubPort,
    target: ClosurePreparationTargetV1,
    evidence: ClosurePreparationEvidenceV1,
    preparation_run_id: int,
    preparation_run_attempt: int,
) -> PreparedClosurePullRequestV1:
    if preparation_run_id < 1 or preparation_run_attempt < 1:
        raise ClosurePreparationError("workflow run identity must be positive")

    stage_slug = _slug(target.stage_id)
    branch = (
        f"closure/{stage_slug}-{evidence.implementation_merge_sha[:12]}"
        f"-r{preparation_run_id}-a{preparation_run_attempt}"
    )
    evidence_path = (
        f"evidence/governance_closure/{stage_slug}/"
        f"{evidence.implementation_merge_sha}.json"
    )

    client.create_branch(branch, evidence.implementation_merge_sha)
    client.create_text_file(
        branch=branch,
        path=evidence_path,
        content=render_evidence_json(evidence),
        message=f"{target.stage_id} add generated closure evidence",
    )

    current_target_content, target_blob_sha = client.get_text_file(
        ref=branch,
        path=TARGET_PATH,
    )
    parsed = json.loads(current_target_content)
    if not isinstance(parsed, dict):
        raise ClosurePreparationError("branch closure target is not a JSON object")
    branch_target = ClosurePreparationTargetV1.from_dict(parsed)
    if branch_target != target:
        raise ClosurePreparationError("closure target changed while preparing the PR")

    client.update_text_file(
        branch=branch,
        path=TARGET_PATH,
        content=render_disabled_target(target),
        current_sha=target_blob_sha,
        message=f"{target.stage_id} disable completed closure preparation target",
    )

    body = render_pr_body(
        target=target,
        evidence=evidence,
        evidence_path=evidence_path,
        preparation_run_id=preparation_run_id,
    )
    raw_pr = client.create_pull_request(
        title=f"{target.stage_id}: prepared canonical closure evidence",
        body=body,
        head=branch,
        base=BASE_BRANCH,
    )
    number = raw_pr.get("number")
    html_url = raw_pr.get("html_url")
    if not isinstance(number, int) or not isinstance(html_url, str):
        raise ClosurePreparationError("GitHub returned invalid closure PR identity")
    return PreparedClosurePullRequestV1(
        number=number,
        html_url=html_url,
        branch=branch,
        evidence_path=evidence_path,
        evidence_identity=evidence.evidence_identity,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a closure PR from live GitHub evidence")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    target = load_target()
    if not target.enabled:
        print(f"CLOSURE_PREPARATION=SKIPPED_DISABLED stage={target.stage_id}")
        return 0

    baseline_tag, baseline_target = _load_baseline()
    client = ClosurePreparationGitHubClient.from_environment()

    evidence = wait_for_closure_evidence(
        client=client,
        target=target,
        expected_merge_sha=args.source_sha,
        current_run_id=args.run_id,
        baseline_tag=baseline_tag,
        baseline_target_commit=baseline_target,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    prepared = prepare_closure_pr(
        client=client,
        target=target,
        evidence=evidence,
        preparation_run_id=args.run_id,
        preparation_run_attempt=args.run_attempt,
    )
    print(f"CLOSURE_PREPARATION=PASS stage={target.stage_id}")
    print(f"EVIDENCE_IDENTITY={prepared.evidence_identity}")
    print(f"EVIDENCE_PATH={prepared.evidence_path}")
    print(f"CLOSURE_BRANCH={prepared.branch}")
    print(f"CLOSURE_PR={prepared.number}")
    print(f"CLOSURE_PR_URL={prepared.html_url}")
    print("CLOSURE_AUTHORITY=PREPARATION_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
