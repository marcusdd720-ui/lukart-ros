"""GitHub App client for controlling LukArt ROS Actions."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


GITHUB_API = "https://api.github.com"
TOKEN_TTL_SECONDS = 540
POLL_INTERVAL_SECONDS = 5


class GitHubActionsError(RuntimeError):
    """Raised when a GitHub Actions API operation fails."""


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    run_id: int
    status: str
    conclusion: str | None
    html_url: str


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
        self._token: str | None = None
        self._token_expires_at = 0.0

    @classmethod
    def from_environment(cls) -> "GitHubActionsClient":
        import os

        required = (
            "LUKART_ROS_FACTORY_APP_ID",
            "LUKART_ROS_FACTORY_PRIVATE_KEY",
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
            repository=os.environ.get("GITHUB_REPOSITORY", "lukart-ros"),
        )

    def _app_jwt(self) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": self.client_id,
        }
        return str(jwt.encode(payload, self.private_key, algorithm="RS256"))

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
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
            self._token_expires_at = min(expiry, time.time() + TOKEN_TTL_SECONDS)
        else:
            self._token_expires_at = time.time() + TOKEN_TTL_SECONDS
        return token

    def _request(
        self,
        method: str,
        url: str,
        *,
        token: str,
        body: bytes | None = None,
    ) -> dict[str, Any]:
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
                f"GitHub API {method} {url} failed with {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubActionsError(f"GitHub API connection failed: {exc.reason}") from exc
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GitHubActionsError("GitHub returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise GitHubActionsError("GitHub returned an unexpected response")
        return parsed

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

    def dispatch_stage(self, stage: int, *, ref: str = "main") -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/workflows/stage-gate.yml/dispatches",
            body={"ref": ref, "inputs": {"stage": str(stage)}},
        )

    def dispatch_stage_and_find_run(self, stage: int, *, ref: str = "main") -> int:
        started_at = datetime.now(timezone.utc)
        self.dispatch_stage(stage, ref=ref)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            for run in self.list_runs(branch=ref, event="workflow_dispatch"):
                path = run.get("path")
                created_at = run.get("created_at")
                run_id = run.get("id")
                if path != ".github/workflows/stage-gate.yml" or not isinstance(run_id, int):
                    continue
                if not isinstance(created_at, str):
                    continue
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if created >= started_at - timedelta(seconds=5):
                    return run_id
            time.sleep(POLL_INTERVAL_SECONDS)
        raise GitHubActionsError("Dispatched Stage Gate run was not found")

    def list_runs(self, *, branch: str = "main", event: str | None = None) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"branch": branch, "per_page": 20})
        if event:
            query += "&" + urllib.parse.urlencode({"event": event})
        data = self._api("GET", f"/repos/{self.repository}/actions/runs?{query}")
        runs = data.get("workflow_runs", [])
        if not isinstance(runs, list):
            raise GitHubActionsError("GitHub returned invalid workflow_runs")
        return [run for run in runs if isinstance(run, dict)]

    def get_run(self, run_id: int) -> WorkflowResult:
        data = self._api("GET", f"/repos/{self.repository}/actions/runs/{run_id}")
        return WorkflowResult(
            run_id=run_id,
            status=str(data.get("status", "unknown")),
            conclusion=(
                str(data["conclusion"]) if data.get("conclusion") is not None else None
            ),
            html_url=str(data.get("html_url", "")),
        )

    def wait_for_run(self, run_id: int, *, timeout_seconds: int = 1800) -> WorkflowResult:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.get_run(run_id)
            if result.status == "completed":
                return result
            time.sleep(POLL_INTERVAL_SECONDS)
        raise GitHubActionsError(f"Workflow run {run_id} did not complete before timeout")

    def list_jobs(self, run_id: int) -> list[dict[str, Any]]:
        data = self._api("GET", f"/repos/{self.repository}/actions/runs/{run_id}/jobs")
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise GitHubActionsError("GitHub returned invalid jobs")
        return [job for job in jobs if isinstance(job, dict)]

    def get_job_logs(self, job_id: int) -> str:
        request = urllib.request.Request(
            f"{self.api_base}/repos/{self.repository}/actions/jobs/{job_id}/logs",
            method="GET",
        )
        request.add_header("Authorization", f"Bearer {self._installation_token()}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubActionsError(
                f"GitHub logs request failed with {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubActionsError(f"GitHub logs connection failed: {exc.reason}") from exc

    def rerun(self, run_id: int) -> None:
        self._api("POST", f"/repos/{self.repository}/actions/runs/{run_id}/rerun")

    def rerun_failed_jobs(self, run_id: int) -> None:
        self._api(
            "POST",
            f"/repos/{self.repository}/actions/runs/{run_id}/rerun-failed-jobs",
        )

    def cancel(self, run_id: int) -> None:
        self._api("POST", f"/repos/{self.repository}/actions/runs/{run_id}/cancel")

    def list_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        data = self._api(
            "GET", f"/repos/{self.repository}/actions/runs/{run_id}/artifacts"
        )
        artifacts = data.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise GitHubActionsError("GitHub returned invalid artifacts")
        return [artifact for artifact in artifacts if isinstance(artifact, dict)]
