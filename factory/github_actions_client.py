"""GitHub App client for controlling LukArt ROS Actions and bounded authoring."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

GITHUB_API = "https://api.github.com"
TOKEN_TTL_SECONDS = 540
POLL_INTERVAL_SECONDS = 5


class GitHubActionsError(RuntimeError):
    """Raised when a GitHub API operation fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    run_id: int
    status: str
    conclusion: str | None
    html_url: str


@dataclass(frozen=True, slots=True)
class CommitOnBranchResult:
    commit_oid: str
    ref_name: str
    ref_oid: str
    url: str
    client_mutation_id: str | None = None


class GitHubActionsClient:
    """GitHub App client for one repository."""

    def __init__(
        self,
        *,
        app_id: int,
        installation_id: int | None,
        private_key: str,
        repository: str,
        client_id: str | None = None,
        api_base: str = GITHUB_API,
        graphql_url: str | None = None,
    ) -> None:
        if not private_key.strip():
            raise ValueError("private_key must not be empty")
        if "/" not in repository:
            raise ValueError("repository must use owner/name form")
        self.app_id = app_id
        self.client_id = client_id.strip() if client_id else str(app_id)
        self.installation_id = installation_id
        self.private_key = private_key
        self.repository = repository
        self.api_base = api_base.rstrip("/")
        self.graphql_url = graphql_url or f"{self.api_base}/graphql"
        self._token: str | None = None
        self._token_expires_at = 0.0

    @classmethod
    def from_environment(cls) -> GitHubActionsClient:
        import os

        required = (
            "LUKART_ROS_FACTORY_APP_ID",
            "LUKART_ROS_FACTORY_PRIVATE_KEY",
            "GITHUB_REPOSITORY",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise GitHubActionsError(
                "Missing GitHub App configuration: " + ", ".join(missing)
            )
        installation_raw = os.environ.get("LUKART_ROS_FACTORY_INSTALLATION_ID")
        return cls(
            app_id=int(os.environ[required[0]]),
            installation_id=int(installation_raw) if installation_raw else None,
            private_key=os.environ[required[1]].replace("\\n", "\n"),
            client_id=os.environ.get("LUKART_ROS_FACTORY_CLIENT_ID"),
            repository=os.environ[required[2]],
            graphql_url=os.environ.get("LUKART_ROS_FACTORY_GRAPHQL_URL"),
        )

    def _app_jwt(self) -> str:
        now = datetime.now(UTC)
        payload = {
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": self.client_id,
        }
        return str(jwt.encode(payload, self.private_key, algorithm="RS256"))

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: str,
        body: bytes | None = None,
    ) -> Any:
        request = urllib.request.Request(url, method=method, data=body)
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubActionsError(
                f"GitHub API {method} {url} failed with {exc.code}: {detail}",
                status_code=exc.code,
                response_body=detail,
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubActionsError(
                f"GitHub API connection failed: {exc.reason}"
            ) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GitHubActionsError("GitHub returned invalid JSON") from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        token: str,
        body: bytes | None = None,
    ) -> dict[str, Any]:
        parsed = self._request_json(method, url, token=token, body=body)
        if not isinstance(parsed, dict):
            raise GitHubActionsError("GitHub returned an unexpected response")
        return parsed

    def _request_list(
        self,
        method: str,
        url: str,
        *,
        token: str,
        body: bytes | None = None,
    ) -> list[dict[str, Any]]:
        parsed = self._request_json(method, url, token=token, body=body)
        if not isinstance(parsed, list) or not all(
            isinstance(item, dict) for item in parsed
        ):
            raise GitHubActionsError("GitHub returned an unexpected list response")
        return parsed

    def _resolve_installation_id(self) -> int:
        url = f"{self.api_base}/repos/{self.repository}/installation"
        data = self._request("GET", url, token=self._app_jwt())
        installation_id = data.get("id")
        if not isinstance(installation_id, int):
            raise GitHubActionsError("GitHub did not return a valid installation ID")
        self.installation_id = installation_id
        return installation_id

    def _installation_token(self) -> str:
        if self._token is not None and time.time() < self._token_expires_at:
            return self._token

        installation_id = self.installation_id or self._resolve_installation_id()
        url = f"{self.api_base}/app/installations/{installation_id}/access_tokens"
        body = json.dumps(
            {"repositories": [self.repository.split("/", 1)[1]]}
        ).encode()
        data = self._request("POST", url, token=self._app_jwt(), body=body)
        token = data.get("token")
        expires_at = data.get("expires_at")
        if not isinstance(token, str) or not token:
            raise GitHubActionsError("GitHub did not return an installation token")
        self._token = token
        if isinstance(expires_at, str):
            expiry = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            ).timestamp()
            self._token_expires_at = min(
                expiry, time.time() + TOKEN_TTL_SECONDS
            )
        else:
            self._token_expires_at = time.time() + TOKEN_TTL_SECONDS
        return token

    def _api(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        return self._request(
            method,
            f"{self.api_base}{path}",
            token=self._installation_token(),
            body=data,
        )

    def _api_list(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        data = None if body is None else json.dumps(body).encode()
        return self._request_list(
            method,
            f"{self.api_base}{path}",
            token=self._installation_token(),
            body=data,
        )

    def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        payload = json.dumps(
            {"query": query, "variables": variables},
            separators=(",", ":"),
        ).encode()
        response = self._request(
            "POST",
            self.graphql_url,
            token=self._installation_token(),
            body=payload,
        )
        errors = response.get("errors")
        if errors:
            raise GitHubActionsError(
                "GitHub GraphQL returned errors: "
                + json.dumps(errors, sort_keys=True, ensure_ascii=False)
            )
        data = response.get("data")
        if not isinstance(data, dict):
            raise GitHubActionsError("GitHub GraphQL did not return data")
        return data

    def dispatch_stage(self, stage: int, *, ref: str = "main") -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/workflows/stage-gate.yml/dispatches",
            body={"ref": ref, "inputs": {"stage": str(stage)}},
        )

    def dispatch_stage_and_find_run(
        self,
        stage: int,
        *,
        ref: str = "main",
    ) -> int:
        started_at = datetime.now(UTC)
        self.dispatch_stage(stage, ref=ref)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            for run in self.list_runs(branch=ref, event="workflow_dispatch"):
                path = run.get("path")
                created_at = run.get("created_at")
                run_id = run.get("id")
                if (
                    path != ".github/workflows/stage-gate.yml"
                    or not isinstance(run_id, int)
                ):
                    continue
                if not isinstance(created_at, str):
                    continue
                created = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                )
                if created >= started_at - timedelta(seconds=5):
                    return run_id
            time.sleep(POLL_INTERVAL_SECONDS)
        raise GitHubActionsError("Dispatched Stage Gate run was not found")

    def list_runs(
        self,
        *,
        branch: str = "main",
        event: str | None = None,
    ) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"branch": branch, "per_page": 20})
        if event:
            query += "&" + urllib.parse.urlencode({"event": event})
        data = self._api(
            "GET",
            f"/repos/{self.repository}/actions/runs?{query}",
        )
        runs = data.get("workflow_runs", [])
        if not isinstance(runs, list):
            raise GitHubActionsError("GitHub returned invalid workflow_runs")
        return [run for run in runs if isinstance(run, dict)]

    def get_run(self, run_id: int) -> WorkflowResult:
        data = self._api(
            "GET",
            f"/repos/{self.repository}/actions/runs/{run_id}",
        )
        return WorkflowResult(
            run_id=run_id,
            status=str(data.get("status", "unknown")),
            conclusion=(
                str(data["conclusion"])
                if data.get("conclusion") is not None
                else None
            ),
            html_url=str(data.get("html_url", "")),
        )

    def wait_for_run(
        self,
        run_id: int,
        *,
        timeout_seconds: int = 1800,
    ) -> WorkflowResult:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.get_run(run_id)
            if result.status == "completed":
                return result
            time.sleep(POLL_INTERVAL_SECONDS)
        raise GitHubActionsError(
            f"Workflow run {run_id} did not complete before timeout"
        )

    def list_jobs(self, run_id: int) -> list[dict[str, Any]]:
        data = self._api(
            "GET",
            f"/repos/{self.repository}/actions/runs/{run_id}/jobs",
        )
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise GitHubActionsError("GitHub returned invalid jobs")
        return [job for job in jobs if isinstance(job, dict)]

    def get_job_logs(self, job_id: int) -> str:
        request = urllib.request.Request(
            f"{self.api_base}/repos/{self.repository}/actions/jobs/{job_id}/logs",
            method="GET",
        )
        request.add_header(
            "Authorization",
            f"Bearer {self._installation_token()}",
        )
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubActionsError(
                f"GitHub logs request failed with {exc.code}: {detail}",
                status_code=exc.code,
                response_body=detail,
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubActionsError(
                f"GitHub logs connection failed: {exc.reason}"
            ) from exc

    def rerun(self, run_id: int) -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/runs/{run_id}/rerun",
        )

    def rerun_failed_jobs(self, run_id: int) -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/runs/{run_id}/rerun-failed-jobs",
        )

    def cancel(self, run_id: int) -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/runs/{run_id}/cancel",
        )

    def list_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        data = self._api(
            "GET",
            f"/repos/{self.repository}/actions/runs/{run_id}/artifacts",
        )
        artifacts = data.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise GitHubActionsError("GitHub returned invalid artifacts")
        return [
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict)
        ]

    def get_ref(self, branch: str) -> dict[str, Any]:
        if not branch:
            raise ValueError("branch must not be empty")
        encoded = urllib.parse.quote(branch, safe="/")
        return self._api(
            "GET",
            f"/repos/{self.repository}/git/ref/heads/{encoded}",
        )

    def get_ref_or_none(self, branch: str) -> dict[str, Any] | None:
        try:
            return self.get_ref(branch)
        except GitHubActionsError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_ref_sha(self, branch: str) -> str:
        data = self.get_ref(branch)
        obj = data.get("object")
        if not isinstance(obj, dict):
            raise GitHubActionsError("GitHub ref response has no object")
        sha = obj.get("sha")
        if not isinstance(sha, str) or not sha:
            raise GitHubActionsError("GitHub ref response has no valid SHA")
        return sha

    def create_ref(self, branch: str, sha: str) -> dict[str, Any]:
        if not branch:
            raise ValueError("branch must not be empty")
        if not sha:
            raise ValueError("sha must not be empty")
        return self._api(
            "POST",
            f"/repos/{self.repository}/git/refs",
            body={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    def get_commit(self, sha: str) -> dict[str, Any]:
        if not sha:
            raise ValueError("sha must not be empty")
        encoded = urllib.parse.quote(sha, safe="")
        return self._api(
            "GET",
            f"/repos/{self.repository}/commits/{encoded}",
        )

    def get_commit_verification(self, sha: str) -> dict[str, Any]:
        data = self.get_commit(sha)
        commit = data.get("commit")
        if not isinstance(commit, dict):
            raise GitHubActionsError(
                "GitHub commit response has no commit object"
            )
        verification = commit.get("verification")
        if not isinstance(verification, dict):
            raise GitHubActionsError(
                "GitHub commit response has no verification object"
            )
        return verification

    def get_commit_parent_shas(self, sha: str) -> list[str]:
        data = self.get_commit(sha)
        parents = data.get("parents")
        if not isinstance(parents, list):
            raise GitHubActionsError(
                "GitHub commit response has no valid parents"
            )
        result: list[str] = []
        for parent in parents:
            if not isinstance(parent, dict):
                raise GitHubActionsError(
                    "GitHub commit response contains an invalid parent"
                )
            parent_sha = parent.get("sha")
            if not isinstance(parent_sha, str) or not parent_sha:
                raise GitHubActionsError(
                    "GitHub commit response contains a parent without SHA"
                )
            result.append(parent_sha)
        return result

    def compare_commits(
        self,
        base: str,
        head: str,
    ) -> dict[str, Any]:
        if not base or not head:
            raise ValueError("base and head must not be empty")
        base_encoded = urllib.parse.quote(base, safe="")
        head_encoded = urllib.parse.quote(head, safe="")
        return self._api(
            "GET",
            (
                f"/repos/{self.repository}/compare/"
                f"{base_encoded}...{head_encoded}"
            ),
        )

    def get_pull_request(self, number: int) -> dict[str, Any]:
        if number <= 0:
            raise ValueError("number must be positive")
        return self._api(
            "GET",
            f"/repos/{self.repository}/pulls/{number}",
        )

    def list_open_pull_requests(
        self,
        *,
        head_branch: str | None = None,
        base_branch: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "state": "open",
            "per_page": 100,
        }
        if head_branch:
            owner = self.repository.split("/", 1)[0]
            params["head"] = f"{owner}:{head_branch}"
        if base_branch:
            params["base"] = base_branch
        query = urllib.parse.urlencode(params)
        return self._api_list(
            "GET",
            f"/repos/{self.repository}/pulls?{query}",
        )

    def create_pull_request(
        self,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("title must not be empty")
        if not head:
            raise ValueError("head must not be empty")
        if not base:
            raise ValueError("base must not be empty")
        return self._api(
            "POST",
            f"/repos/{self.repository}/pulls",
            body={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
            },
        )

    def list_check_runs(self, ref: str) -> list[dict[str, Any]]:
        if not ref:
            raise ValueError("ref must not be empty")
        encoded = urllib.parse.quote(ref, safe="")
        data = self._api(
            "GET",
            (
                f"/repos/{self.repository}/commits/"
                f"{encoded}/check-runs?per_page=100"
            ),
        )
        check_runs = data.get("check_runs")
        if not isinstance(check_runs, list):
            raise GitHubActionsError(
                "GitHub returned invalid check_runs"
            )
        return [
            check_run
            for check_run in check_runs
            if isinstance(check_run, dict)
        ]

    def create_commit_on_branch(
        self,
        *,
        branch: str,
        expected_head_oid: str,
        message_headline: str,
        additions: dict[str, str],
        deletions: tuple[str, ...] = (),
        operation_id: str | None = None,
        message_body: str | None = None,
    ) -> CommitOnBranchResult:
        if not branch:
            raise ValueError("branch must not be empty")
        if not expected_head_oid:
            raise ValueError("expected_head_oid must not be empty")
        if not message_headline.strip():
            raise ValueError("message_headline must not be empty")
        if not additions and not deletions:
            raise ValueError("at least one file change is required")

        deletion_paths = list(deletions)
        if len(deletion_paths) != len(set(deletion_paths)):
            raise ValueError("deletion paths must be unique")
        overlap = set(additions).intersection(deletion_paths)
        if overlap:
            raise ValueError(
                "paths cannot appear in both additions and deletions: "
                + ", ".join(sorted(overlap))
            )

        encoded_additions: list[dict[str, str]] = []
        for path in sorted(additions):
            if not path or path.startswith("/"):
                raise ValueError(
                    "addition paths must be non-empty repository-relative paths"
                )
            encoded_additions.append(
                {
                    "path": path,
                    "contents": base64.b64encode(
                        additions[path].encode("utf-8")
                    ).decode("ascii"),
                }
            )

        encoded_deletions: list[dict[str, str]] = []
        for path in sorted(deletion_paths):
            if not path or path.startswith("/"):
                raise ValueError(
                    "deletion paths must be non-empty repository-relative paths"
                )
            encoded_deletions.append({"path": path})

        file_changes: dict[str, Any] = {}
        if encoded_additions:
            file_changes["additions"] = encoded_additions
        if encoded_deletions:
            file_changes["deletions"] = encoded_deletions

        message: dict[str, str] = {"headline": message_headline}
        if message_body:
            message["body"] = message_body

        input_payload: dict[str, Any] = {
            "branch": {
                "repositoryNameWithOwner": self.repository,
                "branchName": branch,
            },
            "message": message,
            "expectedHeadOid": expected_head_oid,
            "fileChanges": file_changes,
        }
        if operation_id:
            input_payload["clientMutationId"] = operation_id

        mutation = """
        mutation CreateCommitOnBranch($input: CreateCommitOnBranchInput!) {
          createCommitOnBranch(input: $input) {
            clientMutationId
            commit {
              oid
              url
            }
            ref {
              name
              target {
                oid
              }
            }
          }
        }
        """
        data = self._graphql(
            mutation,
            {"input": input_payload},
        )
        payload = data.get("createCommitOnBranch")
        if not isinstance(payload, dict):
            raise GitHubActionsError(
                "GitHub GraphQL did not return createCommitOnBranch payload"
            )

        commit = payload.get("commit")
        ref = payload.get("ref")
        if not isinstance(commit, dict) or not isinstance(ref, dict):
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid commit/ref payload"
            )

        commit_oid = commit.get("oid")
        commit_url = commit.get("url")
        ref_name = ref.get("name")
        target = ref.get("target")
        if not isinstance(target, dict):
            raise GitHubActionsError(
                "GitHub GraphQL returned a ref without target"
            )
        ref_oid = target.get("oid")

        if not isinstance(commit_oid, str) or not commit_oid:
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid commit oid"
            )
        if not isinstance(commit_url, str):
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid commit url"
            )
        if not isinstance(ref_name, str) or not ref_name:
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid ref name"
            )
        if not isinstance(ref_oid, str) or not ref_oid:
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid ref oid"
            )
        if ref_oid != commit_oid:
            raise GitHubActionsError(
                "GitHub GraphQL ref target does not match created commit"
            )

        returned_operation_id = payload.get("clientMutationId")
        if returned_operation_id is not None and not isinstance(
            returned_operation_id,
            str,
        ):
            raise GitHubActionsError(
                "GitHub GraphQL returned an invalid clientMutationId"
            )
        if (
            operation_id is not None
            and returned_operation_id != operation_id
        ):
            raise GitHubActionsError(
                "GitHub GraphQL clientMutationId mismatch"
            )

        return CommitOnBranchResult(
            commit_oid=commit_oid,
            ref_name=ref_name,
            ref_oid=ref_oid,
            url=commit_url,
            client_mutation_id=returned_operation_id,
        )