from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from core.governance_closure_v1 import REQUIRED_PR_WORKFLOWS_V1
from factory.closure_preparation import (
    REQUIRED_POST_MERGE_WORKFLOWS_V1,
    ClosurePreparationError,
    ClosurePreparationGitHubClient,
    ClosurePreparationTargetV1,
    collect_closure_evidence,
    prepare_closure_pr,
    render_disabled_target,
)

HEAD = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40
TAG_OBJECT = "d" * 40
BASELINE_TARGET = "e" * 40
STAGE_WORKFLOW = "GOV-AUTO-01 Closure Preparation"


def _run(run_id: int, name: str, sha: str, *, event: str = "pull_request") -> dict[str, Any]:
    return {
        "id": run_id,
        "name": name,
        "event": event,
        "status": "completed",
        "conclusion": "success",
        "head_sha": sha,
    }


def _target(*, enabled: bool = True) -> ClosurePreparationTargetV1:
    return ClosurePreparationTargetV1(
        stage_id="GOV-AUTO-01",
        next_stage_id="OPR-01",
        implementation_pr=178,
        architecture_doc="docs/GOVERNANCE_CLOSURE_AUTOMATION_V1.md",
        enabled=enabled,
    )


class FakeClient:
    repository = "owner/repo"

    def __init__(self) -> None:
        self.main_sha = MERGE
        self.baseline_target = BASELINE_TARGET
        self.latest_release = "v1.0.1"
        self.pr_runs = [
            _run(index + 1, name, HEAD)
            for index, name in enumerate(REQUIRED_PR_WORKFLOWS_V1)
        ] + [_run(100, STAGE_WORKFLOW, HEAD)]
        self.post_runs = [
            _run(index + 200, name, MERGE, event="push")
            for index, name in enumerate(REQUIRED_POST_MERGE_WORKFLOWS_V1)
        ] + [_run(400, STAGE_WORKFLOW, MERGE, event="push")]
        self.created_branch: tuple[str, str] | None = None
        self.created_files: list[tuple[str, str, str, str]] = []
        self.updated_files: list[tuple[str, str, str, str, str]] = []
        self.created_pr: dict[str, str] | None = None

    def get_pull_request(self, number: int) -> dict[str, Any]:
        assert number == 178
        return {
            "merged": True,
            "merge_commit_sha": MERGE,
            "head": {"sha": HEAD},
        }

    def get_commit(self, sha: str) -> dict[str, Any]:
        assert sha == MERGE
        return {"parents": [{"sha": BASE}, {"sha": HEAD}]}

    def get_ref(self, ref: str) -> dict[str, Any]:
        if ref == "heads/main":
            return {"object": {"sha": self.main_sha, "type": "commit"}}
        if ref == "tags/v1.0.1":
            return {"object": {"sha": TAG_OBJECT, "type": "tag"}}
        raise AssertionError(ref)

    def get_tag_object(self, sha: str) -> dict[str, Any]:
        assert sha == TAG_OBJECT
        return {"object": {"sha": self.baseline_target, "type": "commit"}}

    def get_latest_release(self) -> dict[str, Any]:
        return {"tag_name": self.latest_release}

    def list_runs_for_sha(
        self, sha: str, *, event: str | None = None
    ) -> list[dict[str, Any]]:
        if sha == HEAD:
            assert event == "pull_request"
            return list(self.pr_runs)
        assert sha == MERGE
        assert event is None
        return list(self.post_runs)

    def create_branch(self, branch: str, sha: str) -> None:
        self.created_branch = (branch, sha)

    def create_text_file(
        self, *, branch: str, path: str, content: str, message: str
    ) -> None:
        self.created_files.append((branch, path, content, message))

    def update_text_file(
        self,
        *,
        branch: str,
        path: str,
        content: str,
        current_sha: str,
        message: str,
    ) -> None:
        self.updated_files.append((branch, path, content, current_sha, message))

    def get_text_file(self, *, ref: str, path: str) -> tuple[str, str]:
        assert path == "config/closure_preparation_target.json"
        return json.dumps(_target().canonical_dict()), "f" * 40

    def create_pull_request(
        self, *, title: str, body: str, head: str, base: str
    ) -> dict[str, Any]:
        self.created_pr = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
        return {"number": 201, "html_url": "https://github.com/owner/repo/pull/201"}


def _evidence(client: FakeClient | None = None):
    client = client or FakeClient()
    return collect_closure_evidence(
        client=client,
        target=_target(),
        expected_merge_sha=MERGE,
        current_run_id=None,
        baseline_tag="v1.0.1",
        baseline_target_commit=BASELINE_TARGET,
    )


def test_live_evidence_is_deterministic_and_keeps_additional_successful_workflows() -> None:
    first = _evidence()
    second = _evidence()

    assert first == second
    assert first.evidence_identity == second.evidence_identity
    assert first.governance_report_identity == second.governance_report_identity
    assert STAGE_WORKFLOW in {run.name for run in first.pr_workflows}
    assert STAGE_WORKFLOW in {run.name for run in first.post_merge_workflows}
    assert first.latest_release_tag == "v1.0.1"


def test_missing_canonical_pr_workflow_fails_closed() -> None:
    client = FakeClient()
    client.pr_runs = client.pr_runs[1:]

    with pytest.raises(ClosurePreparationError, match="missing required workflows"):
        _evidence(client)


def test_any_observed_failed_pr_workflow_fails_closed() -> None:
    client = FakeClient()
    client.pr_runs[-1]["conclusion"] = "failure"

    with pytest.raises(ClosurePreparationError, match="is not success"):
        _evidence(client)


def test_nonterminal_post_merge_run_does_not_become_pass() -> None:
    client = FakeClient()
    client.post_runs[-1]["status"] = "in_progress"
    client.post_runs[-1]["conclusion"] = None

    with pytest.raises(ClosurePreparationError, match="conclusion is invalid"):
        _evidence(client)


def test_main_drift_fails_closed() -> None:
    client = FakeClient()
    client.main_sha = "f" * 40

    with pytest.raises(ClosurePreparationError, match="live main drifted"):
        _evidence(client)


def test_baseline_target_drift_fails_closed() -> None:
    client = FakeClient()
    client.baseline_target = "f" * 40

    with pytest.raises(ClosurePreparationError, match="baseline target drift"):
        _evidence(client)


def test_latest_release_drift_fails_closed() -> None:
    client = FakeClient()
    client.latest_release = "v1.1.0"

    with pytest.raises(ClosurePreparationError, match="latest release drift"):
        _evidence(client)


def test_disabled_target_cannot_collect_closure_evidence() -> None:
    with pytest.raises(ClosurePreparationError, match="target is disabled"):
        collect_closure_evidence(
            client=FakeClient(),
            target=_target(enabled=False),
            expected_merge_sha=MERGE,
            current_run_id=None,
            baseline_tag="v1.0.1",
            baseline_target_commit=BASELINE_TARGET,
        )


def test_preparer_creates_evidence_disables_target_and_opens_preparation_only_pr() -> None:
    client = FakeClient()
    evidence = _evidence(client)

    prepared = prepare_closure_pr(
        client=client,
        target=_target(),
        evidence=evidence,
        preparation_run_id=12345,
        preparation_run_attempt=2,
    )

    assert client.created_branch == (
        "closure/gov-auto-01-cccccccccccc-r12345-a2",
        MERGE,
    )
    assert len(client.created_files) == 1
    _, evidence_path, content, _ = client.created_files[0]
    parsed = json.loads(content)
    assert parsed["result"] == "PREPARED_NOT_CLOSED"
    assert parsed["authority"] == "closure-preparation-only"
    assert parsed["evidence_identity"] == evidence.evidence_identity
    assert evidence_path == prepared.evidence_path

    assert len(client.updated_files) == 1
    disabled = json.loads(client.updated_files[0][2])
    assert disabled["enabled"] is False

    assert client.created_pr is not None
    assert "PREPARED / NOT CLOSED" in client.created_pr["body"]
    assert "guarded exact-head merge" in client.created_pr["body"]
    assert prepared.number == 201
    assert prepared.evidence_identity == evidence.evidence_identity


def test_disabled_target_render_is_strict_and_preserves_identity_fields() -> None:
    raw = json.loads(render_disabled_target(_target()))

    assert raw == {
        "architecture_doc": "docs/GOVERNANCE_CLOSURE_AUTOMATION_V1.md",
        "enabled": False,
        "implementation_pr": 178,
        "next_stage_id": "OPR-01",
        "schema": "lukart.closure-preparation-target.v1",
        "stage_id": "GOV-AUTO-01",
    }


def test_github_adapter_lists_runs_by_exact_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ClosurePreparationGitHubClient(
        app_id=1,
        installation_id=2,
        private_key="key",
        repository="owner/repo",
    )
    captured: dict[str, Any] = {}

    def fake_api(
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        captured.update({"method": method, "path": path, "body": body})
        return {"workflow_runs": []}

    monkeypatch.setattr(client, "_api", fake_api)

    assert client.list_runs_for_sha(HEAD, event="pull_request") == []
    assert captured["method"] == "GET"
    assert f"head_sha={HEAD}" in captured["path"]
    assert "event=pull_request" in captured["path"]


def test_github_adapter_encodes_text_file_for_contents_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClosurePreparationGitHubClient(
        app_id=1,
        installation_id=2,
        private_key="key",
        repository="owner/repo",
    )
    captured: dict[str, Any] = {}

    def fake_api(
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        captured.update({"method": method, "path": path, "body": body})
        return {}

    monkeypatch.setattr(client, "_api", fake_api)

    client.create_text_file(
        branch="closure/test",
        path="evidence/example.json",
        content="{\"ok\":true}\n",
        message="test",
    )

    assert captured["method"] == "PUT"
    body = captured["body"]
    assert isinstance(body, dict)
    decoded = base64.b64decode(str(body["content"])).decode("utf-8")
    assert decoded == "{\"ok\":true}\n"
    assert body["branch"] == "closure/test"


def test_github_adapter_requires_scoped_closure_pr_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LUKART_ROS_CLOSURE_PR_TOKEN", raising=False)
    client = ClosurePreparationGitHubClient(
        app_id=1,
        installation_id=2,
        private_key="key",
        repository="owner/repo",
    )

    with pytest.raises(ClosurePreparationError, match="scoped closure PR token"):
        client.create_pull_request(
            title="test",
            body="body",
            head="closure/test",
            base="main",
        )


def test_github_adapter_uses_scoped_closure_pr_token_only_for_pr_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUKART_ROS_CLOSURE_PR_TOKEN", "scoped-token")
    client = ClosurePreparationGitHubClient(
        app_id=1,
        installation_id=2,
        private_key="app-key",
        repository="owner/repo",
    )
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        *,
        token: str,
        body: bytes | None = None,
    ) -> dict[str, Any]:
        captured.update({"method": method, "url": url, "token": token, "body": body})
        return {"number": 201, "html_url": "https://github.com/owner/repo/pull/201"}

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.create_pull_request(
        title="GOV-AUTO-01 closure",
        body="PREPARED / NOT CLOSED",
        head="closure/test",
        base="main",
    )

    assert result["number"] == 201
    assert captured["method"] == "POST"
    assert captured["token"] == "scoped-token"
    assert captured["url"] == "https://api.github.com/repos/owner/repo/pulls"
    raw_body = captured["body"]
    assert isinstance(raw_body, bytes)
    payload = json.loads(raw_body.decode("utf-8"))
    assert payload["head"] == "closure/test"
    assert payload["base"] == "main"
    assert payload["draft"] is False
