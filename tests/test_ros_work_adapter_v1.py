"""Fail-closed unit tests for ROS -> WORK adapter v1."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import replace
from http.client import HTTPMessage
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.ros_work_adapter_v1 import (
    AdapterConfig,
    AuthorityResolution,
    RosWorkAdapterError,
    RosWorkAdapterV1,
    _map_work_response,
    _NoRedirectHandler,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TENANT_ID = "00000000-0000-4000-8000-000000000001"
_CASE_ID = "00000000-0000-4000-8000-000000000002"
_FOREIGN_TENANT_ID = "00000000-0000-4000-8000-000000000003"
_FOREIGN_CASE_ID = "00000000-0000-4000-8000-000000000004"


_AUTHORITY_MAP = {
    "trusted-host-1": AuthorityResolution(
        authority_ref="trusted-host-1",
        token="work-token-abc",
        admitted_operations=(
            "ros.work.generator.assess.v1",
            "ros.work.generator.execute.v1",
            "ros.work.generator.read-package.v1",
        ),
        tenant_id=_TENANT_ID,
        case_id=_CASE_ID,
    ),
}


def _adapter(tmp_path: Path) -> RosWorkAdapterV1:
    authority_file = tmp_path / "authorities.json"
    authority_file.write_text(
        json.dumps(
            {
                "trusted-host-1": {
                    "token": "work-token-abc",
                    "admitted_operations": list(
                        _AUTHORITY_MAP["trusted-host-1"].admitted_operations
                    ),
                    "tenant_id": _TENANT_ID,
                    "case_id": _CASE_ID,
                }
            }
        ),
        encoding="utf-8",
    )
    config = AdapterConfig(
        trusted_host_url="http://127.0.0.1:8765",
        authority_map_path=authority_file,
    )
    adapter = RosWorkAdapterV1(config)
    # Force load authorities
    adapter._authority_map = _AUTHORITY_MAP
    return adapter


def _base_envelope(operation_id: str = "ros.work.generator.assess.v1") -> dict[str, Any]:
    return {
        "request": {
            "schema_id": "lukart.operation-contract.v1",
            "version": "1.0",
            "operation_id": operation_id,
            "operation": operation_id,
            "input": {},
        },
        "context": {
            "repository": "lukart-ros",
            "branch": "main",
            "worktree": "wt",
            "case_id": _CASE_ID,
            "runtime": "python3.14",
        },
        "preconditions": {
            "authority_ref": "trusted-host-1",
            "lock_ref": "lock-1",
            "expected_head": "a" * 40,
        },
        "constraints": {
            "timeout_ms": 30000,
            "allowed_side_effects": [],
            "privacy_scope": _CASE_ID,
            "evidence_required": [],
        },
        "idempotency": {
            "key": "idempotency-1",
            "replay": "exact",
            "duplicate_handling": "replay-or-block",
        },
        "effects": {
            "declared": [],
            "actual": [],
        },
        "output": {
            "status": None,
            "summary": "",
            "artifacts": [],
        },
        "evidence": {"items": []},
        "errors": {"items": []},
        "privacy": {
            "scope": _CASE_ID,
            "data_classification": "SYNTHETIC",
            "cross_scope_allowed": False,
        },
    }


class TestAdapterConfig:
    @pytest.mark.parametrize(
        "url",
        (
            "http://127.0.0.1.attacker:8765",
            "http://127.0.0.1:8765.evil",
            "http://user@127.0.0.1:8765",
            "http://user:pass@127.0.0.1:8765",
            "http://127.0.0.1:8765/path",
            "http://127.0.0.1:8765?next=https://attacker.invalid",
            "http://127.0.0.1:8765#fragment",
            "https://127.0.0.1:8765",
            "http://localhost:8765",
            "http://127.0.0.2:8765",
            "http://127.0.0.1",
            "http://127.0.0.1:99999",
        ),
    )
    def test_rejects_non_exact_or_malformed_trusted_host(self, url: str) -> None:
        with pytest.raises(RosWorkAdapterError, match="trusted host"):
            AdapterConfig(trusted_host_url=url)

    def test_accepts_exact_loopback_origin_with_ephemeral_port(self) -> None:
        AdapterConfig(trusted_host_url="http://127.0.0.1:54321")

    def test_redirect_handler_never_follows_redirects(self) -> None:
        handler = _NoRedirectHandler()
        assert (
            handler.redirect_request(
                None, None, 302, "Found", {}, "http://attacker.invalid"
            )
            is None
        )


# ---------------------------------------------------------------------------
# Envelope validation
# ---------------------------------------------------------------------------


class TestValidateEnvelope:
    def test_missing_section_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        with pytest.raises(RosWorkAdapterError, match="invalid ROS envelope"):
            adapter.validate_envelope({"request": {}})  # type: ignore[dict-item]

    def test_bad_schema_id_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        envelope["request"]["schema_id"] = "bad"
        with pytest.raises(RosWorkAdapterError, match="invalid ROS envelope"):
            adapter.validate_envelope(envelope)

    def test_valid_envelope_passes(self) -> None:
        adapter = _adapter(Path("/tmp"))
        # Should not raise.
        adapter.validate_envelope(_base_envelope())


# ---------------------------------------------------------------------------
# Operation allowlist
# ---------------------------------------------------------------------------


class TestOperationAllowlist:
    def test_unknown_operation_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope("unknown.operation.v1")
        with pytest.raises(RosWorkAdapterError, match="operation not allowed"):
            adapter.map_request(envelope)

    def test_operation_id_mismatch_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        envelope["request"]["operation"] = "ros.work.generator.execute.v1"
        with pytest.raises(RosWorkAdapterError, match="request.operation must equal"):
            adapter.map_request(envelope)


# ---------------------------------------------------------------------------
# Authority and scope
# ---------------------------------------------------------------------------


class TestAuthorityAndScope:
    def test_missing_authority_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        envelope["preconditions"]["authority_ref"] = "missing"
        with pytest.raises(RosWorkAdapterError, match="authority_ref not admitted"):
            adapter.map_request(envelope)

    def test_scope_mismatch_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        # Authority map expects case-1, but envelope says case-2.
        envelope = _base_envelope()
        envelope["context"]["case_id"] = _FOREIGN_CASE_ID
        with pytest.raises(RosWorkAdapterError, match="tenant/case scope mismatch"):
            adapter.map_request(envelope)

    def test_execute_requires_work_operation(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope("ros.work.generator.execute.v1")
        # input lacks work_operation
        with pytest.raises(RosWorkAdapterError, match="execute.v1 requires input.work_operation"):
            adapter.map_request(envelope)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


class TestMapRequest:
    def test_assess_maps_to_query_core(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        assert mapped.work_route == "query_core"
        assert mapped.work_contract == "urn:lukart:work:CoreQuery:1.0.0"
        assert mapped.work_operation == "GetCaseHead"
        assert mapped.tenant_id == _TENANT_ID
        assert mapped.case_id == _CASE_ID
        assert mapped.token == "work-token-abc"
        assert mapped.admitted is True

    def test_execute_is_blocked_even_when_local_authority_map_admits_it(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope("ros.work.generator.execute.v1")
        envelope["request"]["input"]["work_operation"] = "CreateCase"
        with pytest.raises(RosWorkAdapterError, match="native WORK capability"):
            adapter.map_request(envelope)

    def test_read_package_is_blocked_even_when_local_authority_map_admits_it(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope("ros.work.generator.read-package.v1")
        with pytest.raises(RosWorkAdapterError, match="native WORK capability"):
            adapter.map_request(envelope)

    def test_idempotency_key_propagates(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        assert mapped.idempotency_key == "idempotency-1"
        assert mapped.payload == {
            "contract": "urn:lukart:work:CoreQuery:1.0.0",
            "operation": "GetCaseHead", "tenant_id": _TENANT_ID, "case_id": _CASE_ID,
        }
        assert mapped.case_id == _CASE_ID
        assert mapped.tenant_id == _TENANT_ID

    def test_assess_cannot_override_native_scope(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        envelope["request"]["input"] = {"tenant_id": "foreign-tenant"}
        with pytest.raises(RosWorkAdapterError, match="no caller WORK payload"):
            adapter.map_request(envelope)

    def test_request_digest_is_deterministic(self) -> None:
        adapter = _adapter(Path("/tmp"))
        m1 = adapter.map_request(_base_envelope())
        m2 = adapter.map_request(_base_envelope())
        assert m1.request_digest == m2.request_digest


# ---------------------------------------------------------------------------
# Dispatch (mocked HTTP)
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_success_maps_to_ros_success(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        work_response = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
            mock_build_opener.assert_called_once()
            handlers = mock_build_opener.call_args.args
            assert any(isinstance(item, _NoRedirectHandler) for item in handlers)
            assert any(
                isinstance(item, urllib.request.ProxyHandler)
                and getattr(item, "proxies", None) == {}
                for item in handlers
            )
        assert result.status == "success"
        assert result.summary == "native WORK query CASE_HEAD"
        assert result.work_command_id is None
        assert result.work_event_ids == ()

    @pytest.mark.parametrize(
        "changes",
        (
            {
                "operation_id": "ros.work.generator.execute.v1",
                "work_route": "execute_core",
                "work_contract": "urn:lukart:work:CoreRequest:1.0.0",
                "work_operation": "CreateCase",
                "payload": {
                    "contract": "urn:lukart:work:CoreRequest:1.0.0",
                    "operation": "CreateCase",
                    "tenant_id": _TENANT_ID,
                    "case_id": _CASE_ID,
                },
            },
            {
                "operation_id": "ros.work.generator.read-package.v1",
                "work_route": "query_finalization",
                "work_contract": "urn:lukart:work:FinalizationQuery:1.0.0",
                "work_operation": "ReadFinalArtifact",
                "payload": {
                    "contract": "urn:lukart:work:FinalizationQuery:1.0.0",
                    "operation": "ReadFinalArtifact",
                    "tenant_id": _TENANT_ID,
                    "case_id": _CASE_ID,
                },
            },
            {"work_route": "execute_core"},
            {"work_contract": "urn:lukart:work:CoreRequest:1.0.0"},
            {"work_operation": "CreateCase"},
            {"admitted": False},
            {"token": "untrusted-token"},
            {
                "tenant_id": _FOREIGN_TENANT_ID,
                "payload": {
                    "contract": "urn:lukart:work:CoreQuery:1.0.0",
                    "operation": "GetCaseHead",
                    "tenant_id": _FOREIGN_TENANT_ID,
                    "case_id": _CASE_ID,
                },
            },
            {
                "payload": {
                    "contract": "urn:lukart:work:CoreQuery:1.0.0",
                    "operation": "GetCaseHead",
                    "tenant_id": _TENANT_ID,
                    "case_id": _CASE_ID,
                    "timeout_ms": 1,
                },
            },
            {"request_digest": ""},
        ),
    )
    def test_dispatch_revalidates_public_request_before_http(
        self, tmp_path: Path, changes: dict[str, Any]
    ) -> None:
        adapter = _adapter(tmp_path)
        mapped = adapter.map_request(_base_envelope())
        forged = replace(mapped, **changes)
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            with pytest.raises(RosWorkAdapterError):
                adapter.dispatch(forged)
            mock_build_opener.assert_not_called()

    def test_case_head_wrong_tenant_or_case_fails_closed(self) -> None:
        base = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        for response in (
            dict(base, tenant_id=_FOREIGN_TENANT_ID),
            dict(base, case_id=_FOREIGN_CASE_ID),
            dict(base, tenant_id=None),
            dict(base, case_id=None),
        ):
            result = _map_work_response(
                response, "digest-1",
                expected_operation_id="ros.work.generator.assess.v1",
                expected_tenant_id=_TENANT_ID,
                expected_case_id=_CASE_ID,
            )
            assert result.status == "failure"

    def test_assess_rejects_command_applied_response(self) -> None:
        result = _map_work_response(
            {"state": "APPLIED", "command_id": "unexpected"},
            "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID,
            expected_case_id=_CASE_ID,
        )
        assert result.status == "failure"

    def test_foreign_case_head_response_fails_closed(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        work_response = {
            "result_type": "CASE_HEAD",
            "tenant_id": _FOREIGN_TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
        assert result.status == "failure"

    def test_gate_denied_maps_to_blocked(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        work_response = {"code": "GATE_DENIED", "message": "not admitted"}
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
        assert result.status == "blocked"
        assert result.errors[0]["code"] == "GATE_DENIED"

    def test_http_error_raises(self) -> None:
        adapter = _adapter(Path("/tmp"))
        mapped = adapter.map_request(_base_envelope())
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_opener.open.side_effect = urllib.error.HTTPError(
                "http://127.0.0.1:8765/api/query_core",
                403,
                "Forbidden",
                HTTPMessage(),
                None,
            )
            with pytest.raises(RosWorkAdapterError, match="WORK HTTP error"):
                adapter.dispatch(mapped)


# ---------------------------------------------------------------------------
# End-to-end execute (mocked)
# ---------------------------------------------------------------------------


class TestExecute:
    def test_full_flow_assess(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        work_response = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.execute(envelope)
        assert result.status == "success"
        assert result.summary == "native WORK query CASE_HEAD"

    def test_full_flow_blocked_by_work(self) -> None:
        adapter = _adapter(Path("/tmp"))
        envelope = _base_envelope()
        work_response = {"code": "FORBIDDEN", "message": "HUMAN gate not satisfied"}
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.execute(envelope)
        assert result.status == "blocked"
        assert result.errors[0]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Helper: work response mapping
# ---------------------------------------------------------------------------


class TestMapWorkResponse:
    def test_execute_applied_response_is_not_admitted(self) -> None:
        resp = {"state": "APPLIED", "command_id": "c", "refs": [], "event_ids": []}
        result = _map_work_response(
            resp, "digest-1",
            expected_operation_id="ros.work.generator.execute.v1",
            expected_tenant_id=_TENANT_ID, expected_case_id=_CASE_ID,
        )
        assert result.status == "failure"

    def test_gate_denied(self) -> None:
        resp = {"code": "GATE_DENIED"}
        result = _map_work_response(
            resp, "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID, expected_case_id=_CASE_ID,
        )
        assert result.status == "blocked"

    def test_unexpected_shape(self) -> None:
        result = _map_work_response(
            {"foo": "bar"}, "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID, expected_case_id=_CASE_ID,
        )
        assert result.status == "failure"

    def test_unknown_query_result_type_must_fail_closed(self) -> None:
        result = _map_work_response(
            {"result_type": "UNRECOGNIZED"}, "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID, expected_case_id=_CASE_ID,
        )
        assert result.status == "failure"

    def test_partial_case_head_must_fail_closed(self) -> None:
        result = _map_work_response(
            {
                "result_type": "CASE_HEAD",
                "tenant_id": _TENANT_ID,
                "case_id": _CASE_ID,
                "case_sequence": 1,
            },
            "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID,
            expected_case_id=_CASE_ID,
        )
        assert result.status == "failure"

    def test_case_head_rejects_schema_invalid_response(self) -> None:
        valid = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        invalid_responses = (
            dict(valid, case_sequence=0),
            dict(valid, heads=None),
            dict(
                valid,
                heads=[{"kind": "Unknown", "id": _CASE_ID, "revision": 1}],
            ),
            dict(
                valid,
                heads=[{"kind": "Case", "id": "not-a-uuid", "revision": 1}],
            ),
            dict(
                valid,
                heads=[{"kind": "Case", "id": _CASE_ID, "revision": 0}],
            ),
            dict(
                valid,
                heads=[{"kind": "Case", "id": _CASE_ID, "revision": 1, "extra": True}],
            ),
            dict(valid, extra="unexpected"),
        )
        for response in invalid_responses:
            result = _map_work_response(
                response,
                "digest-1",
                expected_operation_id="ros.work.generator.assess.v1",
                expected_tenant_id=_TENANT_ID,
                expected_case_id=_CASE_ID,
            )
            assert result.status == "failure"

    def test_query_result_type_is_mapped_to_success(self) -> None:
        resp = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        result = _map_work_response(
            resp, "digest-1",
            expected_operation_id="ros.work.generator.assess.v1",
            expected_tenant_id=_TENANT_ID, expected_case_id=_CASE_ID,
        )
        assert result.status == "success"
        assert result.summary == "native WORK query CASE_HEAD"
        assert result.work_command_id is None
        assert result.work_event_ids == ()

def test_dispatch_uses_bounded_timeout_from_ros_constraints():
    adapter = _adapter(Path("/tmp"))
    envelope = _base_envelope()
    envelope["constraints"]["timeout_ms"] = 1250
    mapped = adapter.map_request(envelope)
    work_response = {
        "result_type": "CASE_HEAD",
        "tenant_id": _TENANT_ID,
        "case_id": _CASE_ID,
        "case_sequence": 1,
        "heads": [],
    }
    with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
        mock_opener = MagicMock()
        mock_build_opener.return_value = mock_opener
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(work_response).encode("utf-8")
        mock_opener.open.return_value.__enter__.return_value = mock_resp
        result = adapter.dispatch(mapped)
        assert mapped.timeout_ms == 1250
        assert mock_opener.open.call_args.kwargs["timeout"] == 1.25
    assert result.status == "success"

@pytest.mark.parametrize("timeout_ms", (0, 300001, True, 1.5, "1250", None))
def test_map_request_rejects_invalid_timeout(timeout_ms):
    adapter = _adapter(Path("/tmp"))
    envelope = _base_envelope()
    envelope["constraints"]["timeout_ms"] = timeout_ms
    with pytest.raises(RosWorkAdapterError, match="constraints.timeout_ms"):
        adapter.map_request(envelope)


@pytest.mark.parametrize("timeout_ms", (0, 300001, True, 1.5))
def test_dispatch_rejects_forged_timeout_before_http(timeout_ms):
    adapter = _adapter(Path("/tmp"))
    mapped = adapter.map_request(_base_envelope())
    forged = replace(mapped, timeout_ms=timeout_ms)
    with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
        with pytest.raises(RosWorkAdapterError, match="mapped request is incomplete"):
            adapter.dispatch(forged)
        mock_build_opener.assert_not_called()
