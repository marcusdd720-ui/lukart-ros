from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.case_ledger.contracts import ContentAddress
from core.critical_invariants_v2 import (
    FIV02_MAX_TRACE_STEPS,
    FIV02InvariantId,
    FIV02InvariantTrace,
    FIV02Registry,
    FIV02VerificationError,
    verify_fiv02,
)


def test_reference_registry_is_fixed_content_addressed_and_complete() -> None:
    first = FIV02Registry.reference()
    second = FIV02Registry.reference()

    assert first == second
    assert first.registry_identity == second.registry_identity
    assert tuple(item.invariant_id for item in first.definitions) == tuple(
        sorted(FIV02InvariantId, key=lambda item: item.value)
    )
    first.verify()


def test_fiv02_report_is_deterministic_and_exact_sha_bound(tmp_path: Path) -> None:
    sha = "1" * 40
    first = verify_fiv02(code_sha=sha, expected_code_sha=sha, workspace=tmp_path / "a")
    second = verify_fiv02(code_sha=sha, expected_code_sha=sha, workspace=tmp_path / "b")

    assert first == second
    assert first.report_identity == second.report_identity
    assert first.outcome == "PASS"
    assert len(first.results) == len(FIV02InvariantId)
    assert all(result.outcome == "PASS" for result in first.results)
    assert all(result.trace.points for result in first.results)
    assert all(len(result.trace.points) <= FIV02_MAX_TRACE_STEPS for result in first.results)
    first.verify()

    other = verify_fiv02(
        code_sha="2" * 40,
        expected_code_sha="2" * 40,
        workspace=tmp_path / "c",
    )
    assert other.report_identity != first.report_identity


def test_exact_sha_mismatch_and_malformed_identity_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(FIV02VerificationError, match="does not match"):
        verify_fiv02(
            code_sha="1" * 40,
            expected_code_sha="2" * 40,
            workspace=tmp_path / "mismatch",
        )

    for invalid in ("A" * 40, "g" * 40, "1" * 39, "  " + "1" * 40):
        with pytest.raises(FIV02VerificationError):
            verify_fiv02(
                code_sha=invalid,
                expected_code_sha=invalid,
                workspace=tmp_path / "invalid",
            )


def test_all_six_production_boundary_traces_are_present(tmp_path: Path) -> None:
    report = verify_fiv02(
        code_sha="3" * 40,
        expected_code_sha="3" * 40,
        workspace=tmp_path,
    )
    by_id = {result.invariant_id: result for result in report.results}

    assert set(by_id) == set(FIV02InvariantId)
    assert [point.outcome for point in by_id[FIV02InvariantId.APPEND_ONLY_EXACT_HEAD].trace.points] == [
        "accepted",
        "rejected",
        "accepted",
    ]
    assert [
        point.outcome
        for point in by_id[FIV02InvariantId.CONTENT_IDENTITY_DOMAIN_SEPARATION].trace.points
    ] == ["stable", "separated", "separated"]
    assert [point.outcome for point in by_id[FIV02InvariantId.MIGRATION_PATH_DETERMINISM].trace.points] == [
        "stable",
        "rejected",
        "rejected",
    ]
    assert [point.outcome for point in by_id[FIV02InvariantId.AUTHORIZATION_ISOLATION].trace.points] == [
        "allowed",
        "denied",
        "denied",
        "denied",
        "denied",
    ]
    assert [
        point.outcome
        for point in by_id[FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE].trace.points
    ] == ["built", "equivalent", "equivalent"]
    assert [point.outcome for point in by_id[FIV02InvariantId.RECOVERY_ATOMICITY].trace.points] == [
        "rolled-back",
        "accepted",
    ]


def test_tampered_trace_and_result_identity_are_rejected(tmp_path: Path) -> None:
    report = verify_fiv02(
        code_sha="4" * 40,
        expected_code_sha="4" * 40,
        workspace=tmp_path,
    )
    result = report.results[0]

    bad_trace = replace(
        result.trace,
        trace_identity=ContentAddress.for_value({"tampered": True}),
    )
    with pytest.raises(FIV02VerificationError, match="trace content-address mismatch"):
        bad_trace.verify()

    bad_result = replace(
        result,
        result_identity=ContentAddress.for_value({"tampered": True}),
    )
    with pytest.raises(FIV02VerificationError, match="result content-address mismatch"):
        bad_result.verify()


def test_trace_budget_is_fail_closed() -> None:
    with pytest.raises(FIV02VerificationError, match="trace cannot be empty"):
        FIV02InvariantTrace.build(
            invariant_id=FIV02InvariantId.APPEND_ONLY_EXACT_HEAD,
            points=(),
        )


def test_fiv02_module_does_not_claim_external_authority() -> None:
    source = Path("core/critical_invariants_v2.py").read_text(encoding="utf-8")
    forbidden = (
        "release:publish",
        "requests.",
        "urllib.request",
        "httpx",
        "boto3",
    )
    assert all(token not in source for token in forbidden)
    assert "synthetic" in source
    assert "verification-only" in source
