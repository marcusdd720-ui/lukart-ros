"""Fail-closed unit tests for ROS -> WORK adapter v1."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from http.client import HTTPMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.ros_work_adapter_v1 import (
    MAX_WORK_RESPONSE_BYTES,
    AdapterConfig,
    AuthorityResolution,
    RosWorkAdapterError,
    RosWorkAdapterV1,
    RosWorkResult,
    _DeadlineHTTPHandler,
    _map_work_response,
    _NoRedirectHandler,
    _read_bounded_response,
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


def _adapter(tmp_path: Path, trusted_host_url: str = "http://127.0.0.1:8765") -> RosWorkAdapterV1:
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
        trusted_host_url=trusted_host_url,
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
    def test_missing_section_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        with pytest.raises(RosWorkAdapterError, match="invalid ROS envelope"):
            adapter.validate_envelope({"request": {}})  # type: ignore[dict-item]

    def test_bad_schema_id_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        envelope["request"]["schema_id"] = "bad"
        with pytest.raises(RosWorkAdapterError, match="invalid ROS envelope"):
            adapter.validate_envelope(envelope)

    def test_valid_envelope_passes(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        # Should not raise.
        adapter.validate_envelope(_base_envelope())


# ---------------------------------------------------------------------------
# Operation allowlist
# ---------------------------------------------------------------------------


class TestOperationAllowlist:
    def test_unknown_operation_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope("unknown.operation.v1")
        with pytest.raises(RosWorkAdapterError, match="operation not allowed"):
            adapter.map_request(envelope)

    def test_operation_id_mismatch_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        envelope["request"]["operation"] = "ros.work.generator.execute.v1"
        with pytest.raises(RosWorkAdapterError, match="request.operation must equal"):
            adapter.map_request(envelope)


# ---------------------------------------------------------------------------
# Authority and scope
# ---------------------------------------------------------------------------


class TestAuthorityAndScope:
    def test_missing_authority_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        envelope["preconditions"]["authority_ref"] = "missing"
        with pytest.raises(RosWorkAdapterError, match="authority_ref not admitted"):
            adapter.map_request(envelope)

    def test_scope_mismatch_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        # Authority map expects case-1, but envelope says case-2.
        envelope = _base_envelope()
        envelope["context"]["case_id"] = _FOREIGN_CASE_ID
        with pytest.raises(RosWorkAdapterError, match="tenant/case scope mismatch"):
            adapter.map_request(envelope)

    def test_execute_requires_work_operation(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope("ros.work.generator.execute.v1")
        # input lacks work_operation
        with pytest.raises(RosWorkAdapterError, match="execute.v1 requires input.work_operation"):
            adapter.map_request(envelope)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


class TestMapRequest:
    def test_assess_maps_to_query_core(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        mapped = adapter.map_request(_base_envelope())
        assert mapped.work_route == "query_core"
        assert mapped.work_contract == "urn:lukart:work:CoreQuery:1.0.0"
        assert mapped.work_operation == "GetCaseHead"
        assert mapped.tenant_id == _TENANT_ID
        assert mapped.case_id == _CASE_ID
        assert mapped.token == "work-token-abc"
        assert mapped.admitted is True

    def test_execute_is_blocked_even_when_local_authority_map_admits_it(
        self, tmp_path: Path
    ) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope("ros.work.generator.execute.v1")
        envelope["request"]["input"]["work_operation"] = "CreateCase"
        with pytest.raises(RosWorkAdapterError, match="native WORK capability"):
            adapter.map_request(envelope)

    def test_read_package_is_blocked_even_when_local_authority_map_admits_it(
        self, tmp_path: Path
    ) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope("ros.work.generator.read-package.v1")
        with pytest.raises(RosWorkAdapterError, match="native WORK capability"):
            adapter.map_request(envelope)

    def test_idempotency_key_propagates(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        mapped = adapter.map_request(_base_envelope())
        assert mapped.idempotency_key == "idempotency-1"
        assert mapped.payload == {
            "contract": "urn:lukart:work:CoreQuery:1.0.0",
            "operation": "GetCaseHead", "tenant_id": _TENANT_ID, "case_id": _CASE_ID,
        }
        assert mapped.case_id == _CASE_ID
        assert mapped.tenant_id == _TENANT_ID

    def test_assess_cannot_override_native_scope(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        envelope["request"]["input"] = {"tenant_id": "foreign-tenant"}
        with pytest.raises(RosWorkAdapterError, match="no caller WORK payload"):
            adapter.map_request(envelope)

    def test_request_digest_is_deterministic(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        m1 = adapter.map_request(_base_envelope())
        m2 = adapter.map_request(_base_envelope())
        assert m1.request_digest == m2.request_digest


# ---------------------------------------------------------------------------
# Dispatch (mocked HTTP)
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_success_maps_to_ros_success(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
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
            _response_body = json.dumps(work_response).encode("utf-8")
            mock_resp.headers = {"Content-Length": str(len(_response_body))}
            mock_resp.read1.side_effect = [_response_body, b""]
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
            mock_build_opener.assert_called_once()
            handlers = mock_build_opener.call_args.args
            assert any(isinstance(item, _NoRedirectHandler) for item in handlers)
            assert any(isinstance(item, _DeadlineHTTPHandler) for item in handlers)
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

    def test_foreign_case_head_response_fails_closed(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
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
            _response_body = json.dumps(work_response).encode("utf-8")
            mock_resp.headers = {"Content-Length": str(len(_response_body))}
            mock_resp.read1.side_effect = [_response_body, b""]
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
        assert result.status == "failure"

    def test_gate_denied_maps_to_blocked(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        mapped = adapter.map_request(_base_envelope())
        work_response = {"code": "GATE_DENIED", "message": "not admitted"}
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            _response_body = json.dumps(work_response).encode("utf-8")
            mock_resp.headers = {"Content-Length": str(len(_response_body))}
            mock_resp.read1.side_effect = [_response_body, b""]
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.dispatch(mapped)
        assert result.status == "blocked"
        assert result.errors[0]["code"] == "GATE_DENIED"

    def test_http_error_raises(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
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
    def test_full_flow_assess(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
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
            _response_body = json.dumps(work_response).encode("utf-8")
            mock_resp.headers = {"Content-Length": str(len(_response_body))}
            mock_resp.read1.side_effect = [_response_body, b""]
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            result = adapter.execute(envelope)
        assert result.status == "success"
        assert result.summary == "native WORK query CASE_HEAD"

    def test_full_flow_blocked_by_work(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        work_response = {"code": "FORBIDDEN", "message": "HUMAN gate not satisfied"}
        with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_build_opener.return_value = mock_opener
            mock_resp = MagicMock()
            _response_body = json.dumps(work_response).encode("utf-8")
            mock_resp.headers = {"Content-Length": str(len(_response_body))}
            mock_resp.read1.side_effect = [_response_body, b""]
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

def test_dispatch_uses_bounded_timeout_from_ros_constraints(tmp_path: Path):
    adapter = _adapter(tmp_path)
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
        _response_body = json.dumps(work_response).encode("utf-8")
        mock_resp.headers = {"Content-Length": str(len(_response_body))}
        mock_resp.read1.side_effect = [_response_body, b""]
        mock_opener.open.return_value.__enter__.return_value = mock_resp
        result = adapter.dispatch(mapped)
        assert mapped.timeout_ms == 1250
        assert mock_opener.open.call_args.kwargs["timeout"] == pytest.approx(1.25, abs=0.01)
    assert result.status == "success"

@pytest.mark.parametrize("timeout_ms", (0, 300001, True, 1.5, "1250", None))
def test_map_request_rejects_invalid_timeout(timeout_ms, tmp_path: Path):
    adapter = _adapter(tmp_path)
    envelope = _base_envelope()
    envelope["constraints"]["timeout_ms"] = timeout_ms
    with pytest.raises(RosWorkAdapterError, match="constraints.timeout_ms"):
        adapter.map_request(envelope)


@pytest.mark.parametrize("timeout_ms", (0, 300001, True, 1.5))
def test_dispatch_rejects_forged_timeout_before_http(timeout_ms, tmp_path: Path):
    adapter = _adapter(tmp_path)
    mapped = adapter.map_request(_base_envelope())
    forged = replace(mapped, timeout_ms=timeout_ms)
    with patch("core.ros_work_adapter_v1.urllib.request.build_opener") as mock_build_opener:
        with pytest.raises(RosWorkAdapterError, match="mapped request is incomplete"):
            adapter.dispatch(forged)
        mock_build_opener.assert_not_called()



class TestAdapterHardening:
    def test_file_backed_authority_revocation_is_seen_on_next_call(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        adapter.map_request(envelope)
        (tmp_path / "authorities.json").write_text("{}", encoding="utf-8")
        with pytest.raises(RosWorkAdapterError, match="authority_ref not admitted"):
            adapter.map_request(envelope)

    def test_exact_idempotency_replays_and_changed_context_digest_blocks(
        self, tmp_path: Path
    ) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        result = RosWorkResult(status="success", summary="synthetic read-only result")
        with patch.object(adapter, "dispatch", return_value=result) as dispatch:
            assert adapter.execute(envelope) == result
            assert adapter.execute(envelope) == result
            assert dispatch.call_count == 1
            changed = _base_envelope()
            changed["context"]["branch"] = "different-branch"
            with pytest.raises(RosWorkAdapterError, match="different request digest"):
                adapter.execute(changed)
            assert dispatch.call_count == 1

    def test_failed_dispatch_aborts_reservation_for_safe_retry(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        result = RosWorkResult(status="success", summary="synthetic read-only result")
        with patch.object(
            adapter,
            "dispatch",
            side_effect=[RosWorkAdapterError("temporary transport failure"), result],
        ) as dispatch:
            with pytest.raises(RosWorkAdapterError, match="temporary transport failure"):
                adapter.execute(envelope)
            assert adapter.execute(envelope) == result
            assert dispatch.call_count == 2

    def test_execute_passes_one_absolute_deadline_through_ledger_and_dispatch(
        self, tmp_path: Path
    ) -> None:
        adapter = _adapter(tmp_path)
        envelope = _base_envelope()
        result = RosWorkResult(status="success", summary="synthetic read-only result")
        with patch.object(
            adapter._idempotency_ledger,
            "reserve",
            wraps=adapter._idempotency_ledger.reserve,
        ) as reserve:
            with patch.object(adapter, "dispatch", return_value=result) as dispatch:
                assert adapter.execute(envelope) == result
        assert dispatch.call_args.kwargs["deadline"] == reserve.call_args.args[2]

    def test_response_content_length_over_limit_is_rejected_before_read(self) -> None:
        class Response:
            headers = {"Content-Length": str(MAX_WORK_RESPONSE_BYTES + 1)}

            def read1(self, size: int) -> bytes:
                raise AssertionError("oversized response must be rejected before reading")

        with pytest.raises(RosWorkAdapterError, match="size limit"):
            _read_bounded_response(Response())

    def test_chunked_response_without_content_length_is_bounded(self) -> None:
        class Response:
            headers: dict[str, str] = {}

            def read1(self, size: int) -> bytes:
                return b"x" * size

        with pytest.raises(RosWorkAdapterError, match="size limit"):
            _read_bounded_response(Response())

    def test_small_response_is_read_to_eof(self) -> None:
        class Response:
            headers = {"Content-Length": "2"}

            def __init__(self) -> None:
                self.parts = iter((b"{}", b""))

            def read1(self, size: int) -> bytes:
                return next(self.parts)

        assert _read_bounded_response(Response()) == b"{}"

    def test_chunked_response_obeys_absolute_deadline(self, tmp_path: Path) -> None:
        envelope = _base_envelope()
        envelope["constraints"]["timeout_ms"] = 200
        work_response = {
            "result_type": "CASE_HEAD",
            "tenant_id": _TENANT_ID,
            "case_id": _CASE_ID,
            "case_sequence": 1,
            "heads": [],
        }
        body = json.dumps(work_response).encode("utf-8")
        split = len(body) // 3
        chunks = (body[:split], body[split:2 * split], body[2 * split:])

        class SlowChunkedHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for chunk in chunks:
                    try:
                        self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii") + chunk + b"\r\n")
                        self.wfile.flush()
                        time.sleep(0.12)
                    except OSError:
                        return
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except OSError:
                    return

            def log_message(self, format: str, *args: object) -> None:
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowChunkedHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        adapter = _adapter(
            tmp_path,
            trusted_host_url=f"http://127.0.0.1:{server.server_port}",
        )
        mapped = adapter.map_request(envelope)
        started = time.monotonic()
        try:
            with pytest.raises(RosWorkAdapterError, match="deadline exceeded"):
                adapter.dispatch(mapped)
            assert time.monotonic() - started < 1.0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
