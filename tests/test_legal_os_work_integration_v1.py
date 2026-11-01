"""Synthetic H2 verification for ROS -> WORK integration.

Covers exception redaction at the ROS/WORK handler boundary and the
cross-repo ROS gate to native WORK prerequisite mapping compliance.
No real case data, no credentials, no production activation.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

import pytest

from core.operations import OperationContractError, build_operation_request
from core.operations.legal_os_gate_map_v1 import (
    ROS_SOURCE_SHA,
    WORK_CANDIDATE_SHA,
    all_ros_gates,
    can_promote_from_mapping_only,
    map_ros_gate,
)
from core.operations.legal_os_readonly_v1 import ASSESS, assess_legal_os_readonly
from core.operations.types_v1 import OperationStatus

HEAD = "a" * 40
WORK_SHA = "b" * 40
PRIVACY = "case:legal-os-synthetic"
CASE = "CASE-LEGAL-OS-SYNTHETIC"
TENANT = "tenant-synthetic"
TYPE = "PL-PRE-PAYMENT-1"
SECRET = "PRIVATE-SYNTHETIC-REDACTION-PROBE"


def _snapshot():
    return {
        "tenant_id": TENANT,
        "case_id": CASE,
        "candidate_sha": WORK_SHA,
        "type_id": TYPE,
        "work_state_ref": "work:synthetic:case",
        "work_digest": "c" * 64,
    }


def _request(*, input_payload=None, operation=ASSESS, idem="idem:h2:1"):
    return build_operation_request(
        operation_id="op:h2:001",
        operation=operation,
        input_payload=input_payload or {
            "tenant_id": TENANT,
            "work_case_id": CASE,
            "candidate_sha": WORK_SHA,
            "type_id": TYPE,
        },
        repository="marcusdd720-ui/lukart-ros",
        branch="h2/ros-work-integration",
        worktree="synthetic",
        case_id=CASE,
        runtime="synthetic-pytest",
        authority_ref="auth:opaque:synthetic",
        lock_ref="lock:synthetic",
        expected_head=HEAD,
        timeout_ms=5000,
        allowed_side_effects=[],
        privacy_scope=PRIVACY,
        evidence_required=(),
        idempotency_key=idem,
    )


def _failure_without_leak(execution):
    assert execution["envelope"]["output"]["status"] == OperationStatus.FAILURE.value
    assert SECRET not in str(execution)
    assert execution["envelope"]["evidence"]["items"] == []
    code = execution["envelope"]["errors"]["items"][0]["code"]
    assert code in {"HANDLER_CONTRACT_ERROR", "UNHANDLED_HANDLER_ERROR"}


@pytest.mark.parametrize("origin", ["authority", "reader"])
@pytest.mark.parametrize("exception_type", [OperationContractError, RuntimeError])
def test_host_callback_errors_cannot_export_private_details(origin, exception_type):
    call_order = []

    def resolve(authority, tenant, case, scope):
        call_order.append("resolve")
        assert (authority, tenant, case, scope) == (
            "auth:opaque:synthetic",
            TENANT,
            CASE,
            PRIVACY,
        )
        if origin == "authority":
            raise exception_type(SECRET)
        return object()

    def read(capability, tenant, case, sha, type_id):
        call_order.append("read")
        assert capability is not None
        assert (tenant, case, sha, type_id) == (TENANT, CASE, WORK_SHA, TYPE)
        if origin == "reader":
            raise exception_type(SECRET)
        return _snapshot()

    execution = assess_legal_os_readonly(
        _request(),
        current_head=HEAD,
        privacy_scope=PRIVACY,
        authority_resolver=resolve,
        work_reader=read,
    )
    _failure_without_leak(execution)
    if origin == "authority":
        assert call_order == ["resolve"]
    else:
        assert call_order == ["resolve", "read"]


def test_native_mapping_contract_error_cannot_export_private_details():
    class FailingSnapshot(Mapping[str, object]):
        def __iter__(self):
            raise OperationContractError(SECRET)

        def __len__(self):
            return 1

        def __getitem__(self, key):
            raise OperationContractError(SECRET)

    execution = assess_legal_os_readonly(
        _request(),
        current_head=HEAD,
        privacy_scope=PRIVACY,
        authority_resolver=lambda *_: object(),
        work_reader=lambda *_: FailingSnapshot(),
    )
    _failure_without_leak(execution)


def test_gate_map_identity_and_non_admission():
    assert re.fullmatch(r"[0-9a-f]{40}", ROS_SOURCE_SHA)
    assert re.fullmatch(r"[0-9a-f]{40}", WORK_CANDIDATE_SHA)
    work = {f"HG-{i:02d}" for i in range(1, 10)}
    observed: set[str] = set()
    for gate in all_ros_gates():
        requirements = map_ros_gate(gate)
        assert requirements.ros_gate == gate
        assert requirements.admission == "NOT_ADMITTED"
        assert requirements.ros_only_requirements
        assert set(requirements.work_prerequisites) <= work
        observed.update(requirements.work_prerequisites)
    assert observed == work
    assert not can_promote_from_mapping_only()


def test_gate_map_is_prerequisite_metadata_not_a_verdict():
    for gate in all_ros_gates():
        requirements = map_ros_gate(gate)
        assert requirements.relation == "RELATED_PREREQUISITES_NOT_EQUIVALENCE"
        assert requirements.admission == "NOT_ADMITTED"


def test_unknown_gate_is_rejected():
    with pytest.raises(ValueError, match="LEGAL_OS_UNKNOWN_ROS_GATE"):
        map_ros_gate("G9")
    with pytest.raises(ValueError, match="LEGAL_OS_UNKNOWN_ROS_GATE"):
        map_ros_gate(cast(str, None))


def test_adapter_evidence_reference_matches_digest_binding():
    resolve_calls = 0
    read_calls = 0

    def resolve(authority, tenant, case, scope):
        nonlocal resolve_calls
        resolve_calls += 1
        return object()

    def read(capability, tenant, case, sha, type_id):
        nonlocal read_calls
        read_calls += 1
        return _snapshot()

    execution = assess_legal_os_readonly(
        _request(),
        current_head=HEAD,
        privacy_scope=PRIVACY,
        authority_resolver=resolve,
        work_reader=read,
    )
    assert execution["envelope"]["output"]["status"] == OperationStatus.SUCCESS.value
    items = execution["envelope"]["evidence"]["items"]
    assert items == [{"kind": "work_snapshot", "ref": "work:synthetic:case", "digest": "c" * 64}]
    assert execution["receipt"]["evidence_refs"] == ["work:synthetic:case"]
    assert resolve_calls == 1 and read_calls == 1
