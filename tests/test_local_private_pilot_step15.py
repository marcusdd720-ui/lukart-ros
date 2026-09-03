from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.local_case_store import PrivacyViolation
from validation.local_private_pilot import (
    LocalPilotStatus,
    attest_local_private_pilot,
    prepare_local_private_pilot,
    write_local_pilot_attestation,
)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    data_root = tmp_path / "MVROS-DATA"
    data_root.mkdir()
    return repo, data_root


def test_step15_preparation_does_not_claim_pilot_execution(tmp_path: Path) -> None:
    repo, data_root = _roots(tmp_path)

    attestation = prepare_local_private_pilot(
        case_key="REAL_CASE_LOCAL_1",
        data_root=data_root,
        repo_root=repo,
        validated_sha="a" * 40,
    )

    assert attestation.status is LocalPilotStatus.READY_FOR_LOCAL_EXECUTION
    assert attestation.local_only_execution_attested is True
    assert attestation.pilot_results_recorded is False
    assert attestation.passed is False


def test_step15_records_only_digest_of_private_local_result(tmp_path: Path) -> None:
    repo, data_root = _roots(tmp_path)
    result = data_root / "cases" / "REAL_CASE_LOCAL_1" / "reports" / "pilot.json"
    result.parent.mkdir(parents=True)
    result.write_text("private local pilot payload", encoding="utf-8")

    attestation = attest_local_private_pilot(
        case_key="REAL_CASE_LOCAL_1",
        data_root=data_root,
        repo_root=repo,
        validated_sha="a" * 40,
        result_path=result,
        pipeline_exit_code=0,
        stages_executed=3,
    )

    payload = json.dumps(attestation.canonical_dict(), sort_keys=True)
    assert attestation.status is LocalPilotStatus.PASSED
    assert attestation.passed is True
    assert attestation.pilot_results_recorded is True
    assert len(attestation.result_digest or "") == 64
    assert "REAL_CASE_LOCAL_1" not in payload
    assert str(data_root) not in payload
    assert str(result) not in payload
    assert "private local pilot payload" not in payload


def test_step15_rejects_result_outside_private_data_root(tmp_path: Path) -> None:
    repo, data_root = _roots(tmp_path)
    outside = tmp_path / "outside-result.json"
    outside.write_text("result", encoding="utf-8")

    with pytest.raises(PrivacyViolation, match="private local data root"):
        attest_local_private_pilot(
            case_key="REAL_CASE_LOCAL_1",
            data_root=data_root,
            repo_root=repo,
            validated_sha="a" * 40,
            result_path=outside,
            pipeline_exit_code=0,
            stages_executed=1,
        )


def test_step15_rejects_repository_as_private_data_root(tmp_path: Path) -> None:
    repo, _ = _roots(tmp_path)

    with pytest.raises(PrivacyViolation, match="outside the Git repository"):
        prepare_local_private_pilot(
            case_key="REAL_CASE_LOCAL_1",
            data_root=repo / "private-cases",
            repo_root=repo,
            validated_sha="a" * 40,
        )


def test_step15_privacy_failure_blocks_pass(tmp_path: Path) -> None:
    repo, data_root = _roots(tmp_path)
    result = data_root / "pilot-result.json"
    result.write_text("local-only result", encoding="utf-8")

    attestation = attest_local_private_pilot(
        case_key="REAL_CASE_LOCAL_1",
        data_root=data_root,
        repo_root=repo,
        validated_sha="a" * 40,
        result_path=result,
        pipeline_exit_code=0,
        stages_executed=1,
        pii_committed=True,
    )

    assert attestation.status is LocalPilotStatus.REJECTED
    assert attestation.pii_not_committed is False
    assert attestation.passed is False


def test_step15_attestation_is_persisted_only_outside_repository(tmp_path: Path) -> None:
    repo, data_root = _roots(tmp_path)
    attestation = prepare_local_private_pilot(
        case_key="REAL_CASE_LOCAL_1",
        data_root=data_root,
        repo_root=repo,
        validated_sha="a" * 40,
    )

    path = write_local_pilot_attestation(
        attestation,
        data_root=data_root,
        repo_root=repo,
    )

    assert path.is_file()
    assert data_root.resolve() in path.resolve().parents
    assert repo.resolve() not in path.resolve().parents
    payload = path.read_text(encoding="utf-8")
    assert "REAL_CASE_LOCAL_1" not in payload
