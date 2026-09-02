import base64
import json
from typing import Any

import pytest

from factory.github_actions_client import GitHubActionsClient, GitHubActionsError


TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
TEST-KEY-MATERIAL
-----END PRIVATE KEY-----"""
TEST_APP_ID = 42
TEST_INSTALLATION_ID = 84
TEST_CLIENT_ID = "test-client-id"


def client(monkeypatch: pytest.MonkeyPatch) -> GitHubActionsClient:
    monkeypatch.setenv("LUKART_ROS_FACTORY_APP_ID", str(TEST_APP_ID))
    monkeypatch.setenv("LUKART_ROS_FACTORY_PRIVATE_KEY", TEST_PRIVATE_KEY)
    monkeypatch.setenv("LUKART_ROS_FACTORY_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("LUKART_ROS_FACTORY_INSTALLATION_ID", str(TEST_INSTALLATION_ID))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repository")
    return GitHubActionsClient.from_environment()


def test_environment_configuration_requires_all_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LUKART_ROS_FACTORY_APP_ID", raising=False)
    monkeypatch.delenv("LUKART_ROS_FACTORY_PRIVATE_KEY", raising=False)

    with pytest.raises(GitHubActionsError):
        GitHubActionsClient.from_environment()


def test_environment_configuration_normalizes_private_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LUKART_ROS_FACTORY_APP_ID", str(TEST_APP_ID))
    monkeypatch.setenv("LUKART_ROS_FACTORY_PRIVATE_KEY", TEST_PRIVATE_KEY.replace("\n", "\\n"))

    result = GitHubActionsClient.from_environment()

    assert result.private_key == TEST_PRIVATE_KEY


def test_environment_configuration_uses_optional_client_id(monkeypatch: pytest.MonkeyPatch):
    result = client(monkeypatch)

    assert result.client_id == TEST_CLIENT_ID


def test_app_jwt_uses_string_issuer(monkeypatch: pytest.MonkeyPatch):
    result = client(monkeypatch)

    token = result._app_jwt()
    payload = result._token_decode_for_test(token)

    assert payload["iss"] == TEST_CLIENT_ID
    assert isinstance(payload["iss"], str)


def test_dispatch_stage_uses_workflow_dispatch_contract(monkeypatch: pytest.MonkeyPatch):
    result = client(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_api(method: str, path: str, *, body: dict[str, Any] | None = None):
        captured.update(method=method, path=path, body=body)
        return {}

    monkeypatch.setattr(result, "_api", fake_api)
    result.dispatch_stage(7)

    assert captured == {
        "method": "POST",
        "path": "/repos/owner/repository/actions/workflows/stage-gate.yml/dispatches",
        "body": {"ref": "main", "inputs": {"stage": "7"}},
    }


def test_new_installation_token_shape_is_treated_as_opaque(monkeypatch: pytest.MonkeyPatch):
    result = client(monkeypatch)
    calls: list[tuple[str, str, str]] = []

    def fake_request(method: str, url: str, *, token: str, body=None):
        calls.append((method, url, token))
        return {"token": "opaque-installation-token"}

    monkeypatch.setattr(result, "_request", fake_request)

    token = result._installation_token()

    assert token == "opaque-installation-token"
    assert calls[0][0] == "POST"


def test_workflow_result_parses_completed_success(monkeypatch: pytest.MonkeyPatch):
    result = client(monkeypatch)

    monkeypatch.setattr(
        result,
        "_api",
        lambda *args, **kwargs: {
            "id": 123,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/example/run/123",
        },
    )

    workflow = result.get_run(123)

    assert workflow.run_id == 123
    assert workflow.status == "completed"
    assert workflow.conclusion == "success"


# Kept as a small test-only helper by replacing jwt.decode in the module.
def _token_decode_for_test(self, token: str) -> dict[str, Any]:
    import jwt

    return jwt.decode(token, options={"verify_signature": False})


GitHubActionsClient._token_decode_for_test = _token_decode_for_test
