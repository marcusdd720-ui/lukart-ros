"""Synthetic-only negative and positive tests for read-only LEGAL OS adapter."""
from __future__ import annotations

import copy

import pytest

from core.operations import (
    OperationContractError,
    OperationRuntime,
    build_operation_request,
)
from core.operations.legal_os_readonly_v1 import ASSESS, assess_legal_os_readonly

HEAD = "a" * 40
WORK_SHA = "b" * 40
PRIVACY = "case:legal-os-synthetic"
CASE = "CASE-LEGAL-OS-SYNTHETIC"
TENANT = "tenant-synthetic"
TYPE = "PL-PRE-PAYMENT-1"
DIGEST = "c" * 64


def request(*, input_payload=None, operation=ASSESS, idem="idem:legal:1", effects=()):
    return build_operation_request(
        operation_id="op:legal:001",
        operation=operation,
        input_payload=input_payload or {
            "tenant_id": TENANT,
            "work_case_id": CASE,
            "candidate_sha": WORK_SHA,
            "type_id": TYPE,
        },
        repository="marcusdd720-ui/lukart-ros",
        branch="feature/legal-os-readonly",
        worktree="synthetic",
        case_id=CASE,
        runtime="synthetic-pytest",
        authority_ref="auth:opaque:synthetic",
        lock_ref="lock:synthetic",
        expected_head=HEAD,
        timeout_ms=5000,
        allowed_side_effects=effects,
        privacy_scope=PRIVACY,
        evidence_required=(),
        idempotency_key=idem,
    )


def callbacks():
    calls = {"resolve": 0, "read": 0}

    def resolve(authority, tenant, case, scope):
        calls["resolve"] += 1
        assert (authority, tenant, case, scope) == (
            "auth:opaque:synthetic", TENANT, CASE, PRIVACY
        )
        return object()

    def read(capability, tenant, case, sha, type_id):
        calls["read"] += 1
        assert capability is not None
        assert (tenant, case, sha, type_id) == (TENANT, CASE, WORK_SHA, TYPE)
        return {
            "tenant_id": TENANT,
            "case_id": CASE,
            "candidate_sha": WORK_SHA,
            "type_id": TYPE,
            "work_state_ref": "work:synthetic:case",
            "work_digest": DIGEST,
        }

    return resolve, read, calls


def outcome(execution):
    return execution["envelope"]["output"]["status"]


def test_exact_scoped_read_receipt_never_grants_release():
    resolve, read, calls = callbacks()
    execution = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=read,
    )
    assert outcome(execution) == "success"
    assert execution["envelope"]["effects"]["actual"] == []
    assert execution["envelope"]["evidence"]["items"] == [
        {"kind": "work_snapshot", "ref": "work:synthetic:case", "digest": DIGEST}
    ]
    assert "NOT inferred" in execution["envelope"]["output"]["summary"]
    assert calls == {"resolve": 1, "read": 1}


def test_missing_trusted_host_capability_blocks():
    execution = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
    )
    assert outcome(execution) == "blocked"
    assert execution["envelope"]["evidence"]["items"] == []


def test_unadmitted_native_capability_blocks_before_reader():
    _, read, calls = callbacks()
    execution = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=lambda *_: None, work_reader=read,
    )
    assert outcome(execution) == "blocked"
    assert calls["read"] == 0


@pytest.mark.parametrize("field,value", [
    ("type_id", "PL-COURT-1"),
    ("candidate_sha", "not-a-commit"),
    ("human_approval", "PASS"),
])
def test_unsupported_type_revision_or_supplied_human_approval_rejected(field, value):
    payload = copy.deepcopy(request()["request"]["input"])
    payload[field] = value
    with pytest.raises(OperationContractError):
        assess_legal_os_readonly(
            request(input_payload=payload),
            current_head=HEAD, privacy_scope=PRIVACY,
        )


def test_write_effects_rejected_before_callbacks():
    resolve, read, calls = callbacks()
    with pytest.raises(OperationContractError):
        assess_legal_os_readonly(
            request(effects=("commit",)),
            current_head=HEAD, privacy_scope=PRIVACY,
            authority_resolver=resolve, work_reader=read,
        )
    assert calls == {"resolve": 0, "read": 0}


def test_unknown_operation_rejected():
    with pytest.raises(OperationContractError):
        assess_legal_os_readonly(
            request(operation="ros.work.generator.execute.v1"),
            current_head=HEAD, privacy_scope=PRIVACY,
        )


def test_cross_case_rejected_before_reader():
    payload = dict(request()["request"]["input"])
    payload["work_case_id"] = "CASE-OTHER"
    resolve, read, calls = callbacks()
    with pytest.raises(OperationContractError):
        assess_legal_os_readonly(
            request(input_payload=payload),
            current_head=HEAD, privacy_scope=PRIVACY,
            authority_resolver=resolve, work_reader=read,
        )
    assert calls == {"resolve": 0, "read": 0}


def test_stale_cas_and_privacy_scope_block_before_reader():
    resolve, read, calls = callbacks()
    stale = assess_legal_os_readonly(
        request(idem="idem:stale"), current_head="d" * 40,
        privacy_scope=PRIVACY, authority_resolver=resolve, work_reader=read,
    )
    privacy = assess_legal_os_readonly(
        request(idem="idem:privacy"), current_head=HEAD,
        privacy_scope="case:other", authority_resolver=resolve, work_reader=read,
    )
    assert outcome(stale) == "blocked"
    assert outcome(privacy) == "blocked"
    assert calls == {"resolve": 0, "read": 0}


def test_native_scope_or_sha_mismatch_cannot_be_promoted():
    resolve, read, calls = callbacks()

    def bad_read(*args):
        native = read(*args)
        native["candidate_sha"] = "d" * 40
        return native

    execution = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=bad_read,
    )
    assert outcome(execution) == "blocked"
    assert execution["envelope"]["evidence"]["items"] == []


def test_native_verdict_and_raw_extra_fields_are_not_trusted():
    resolve, read, _ = callbacks()

    def tampered(*args):
        native = read(*args)
        native["legal_approved"] = True
        return native

    execution = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=tampered,
    )
    assert outcome(execution) == "failure"
    assert "legal_approved" not in str(execution)


def test_idempotency_exact_replay_without_re_read():
    resolve, read, calls = callbacks()
    runtime = OperationRuntime()
    first = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=read, runtime=runtime,
    )
    second = assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=read, runtime=runtime,
    )
    assert first == second
    assert calls == {"resolve": 1, "read": 1}


def test_idempotency_different_payload_digest_blocks():
    resolve, read, calls = callbacks()
    runtime = OperationRuntime()
    assess_legal_os_readonly(
        request(), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=read, runtime=runtime,
    )
    other = dict(request()["request"]["input"])
    other["type_id"] = "PL-PRE-REPLY-1"
    blocked = assess_legal_os_readonly(
        request(input_payload=other), current_head=HEAD, privacy_scope=PRIVACY,
        authority_resolver=resolve, work_reader=read, runtime=runtime,
    )
    assert outcome(blocked) == "blocked"
    assert calls == {"resolve": 1, "read": 1}
