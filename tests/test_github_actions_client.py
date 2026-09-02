from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from factory.github_actions_client import GitHubActionsClient, GitHubActionsError


TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
TEST-KEY-MATERIAL
-----END PRIVATE KEY-----"""


def test_environment_configuration_requires_all_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUKART_ROS_FACTORY_APP_ID", raising=False)
    monkeypatch.delenv("LUKART_ROS_FACTORY_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("LUKART_ROS_FACTORY_PRIVATE_KEY", raising=False)

    with pytest.raises(GitHubActionsError, match="Missing GitHub App configuration"):
        GitHubActionsClient.from_environment()


def test_environment_configuration_normalizes_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUKART_ROS_FACTORY_APP_ID", "4804861")
    monkeypatch.setenv("LUKART_ROS_FACTORY_INSTALLATION_ID", "152031980")
    monkeypatch.setenv("LUKART_ROS_FACTORY_PRIVATE_KEY", "line1\\nline2")
    monkeypatch.setenv("GITHUB_REPOSITORY", "marcusdd720-ui/lukart-ros")

    client = GitHubActionsClient.from_environment()

    assert client.app_id == 4804861
    assert client.client_id == "4804861"
    assert client.installation_id == 152031980
    assert client.private_key == "line1\nline2"
    assert client.repository == "marcusdd720-ui/lukart-ros"


def test_environment_configuration_uses_optional_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUKART_ROS_FACTORY_APP_ID", "4804861")
    monkeypatch.setenv("LUKART_ROS_FACTORY_INSTALLATION_ID", "152031980")
    monkeypatch.setenv("LUKART_ROS_FACTORY_PRIVATE_KEY", "key")
    monkeypatch.setenv("LUKART_ROS_FACTORY_CLIENT_ID", "Iv23liXvRDs1jPRRZS5m")

    client = GitHubActionsClient.from_environment()

    assert client.client_id == "Iv23liXvRDs1jPRRZS5m"


def test_app_jwt_uses_string_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubActionsClient(
        app_id=4804861,
        installation_id=152031980,
        private_key=TEST_PRIVATE_KEY,
        repository="marcusdd720-ui/lukart-ros",
    )

    monkeypatch.setattr(
        "factory.github_actions_client.jwt.encode",
        lambda payload, key, algorithm: json.dumps(payload),
    )
    payload = json.loads(client._app_jwt())

    assert payload["iss"] == "4804861"
    assert isinstance(payload["iss"], str)
    assert payload["exp"] > payload["iat"]
    assert payload["exp"] - payload["iat"] <= 600


def test_dispatch_stage_uses_workflow_dispatch_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubActionsClient(
        app_id=1,
        installation_id=2,
        private_key=TEST_PRIVATE_KEY,
        repository="owner/repo",
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        client,
        "_api",
        lambda method, path, body=None: captured.update(
            {"method": method, "path": path, "body": body}
        )
        or {},
    )
    monkeypatch.setattr(client, "_installation_token", lambda: "ghs_example")

    client.dispatch_stage(6)

    assert captured == {
        "method": "POST",
        "path": "/repos/owner/repo/actions/workflows/stage-gate.yml/dispatches",
        "body": {"ref": "main", "inputs": {"stage": "6"}},
    }


def test_new_installation_token_shape_is_treated_as_opaque(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubActionsClient(
        app_id=1,
        installation_id=2,
        private_key=TEST_PRIVATE_KEY,
        repository="owner/repo",
    )
    token = "ghs_" + base64.urlsafe_b64encode(b"x" * 390).decode().rstrip("=")
    monkeypatch.setattr(client, "_app_jwt", lambda: "jwt")
    monkeypatch.setattr(
        client,
        "_request",
        lambda method, url, **kwargs: {
            "token": token,
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert client._installation_token() == token


def test_workflow_result_parses_completed_success() -> None:
    client = GitHubActionsClient(
        app_id=1,
        installation_id=2,
        private_key=TEST_PRIVATE_KEY,
        repository="owner/repo",
    )

    monkeypatch_data = {
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://github.com/owner/repo/actions/runs/123",
    }

    client._api = lambda method, path, body=None: monkeypatch_data  # type: ignore[method-assign]
    result = client.get_run(123)

    assert result.run_id == 123
    assert result.status == "completed"
    assert result.conclusion == "success"
    assert result.html_url.endswith("/123")
