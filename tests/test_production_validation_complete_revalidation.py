from __future__ import annotations

import json
from pathlib import Path

import pytest

import factory.production_validation_orchestrator as pvo
from tests.test_release_candidate_gate import (
    _seed_steps_1_through_19,
    _write_json,
    _write_release_candidate,
)


def _seed_complete_program(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    provenance_dir = _seed_steps_1_through_19(root, monkeypatch)
    chain_digest, chain_decision = pvo.production_validation_chain_digest(root)
    assert chain_decision is None
    assert chain_digest is not None
    _write_release_candidate(root, chain_digest, provenance_dir)

    state_path = root / "production_validation_state.json"
    _write_json(
        state_path,
        {
            "current_step": 20,
            "last_completed_step": 20,
            "last_result": "PASS",
            "status": "COMPLETE",
        },
    )
    return state_path


def _state(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_complete_intact_chain_is_revalidated_and_remains_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = _seed_complete_program(tmp_path, monkeypatch)

    decision = pvo.apply_current_step(tmp_path, state_path)

    assert decision.passed is True
    assert decision.code == "PROGRAM_COMPLETE"
    assert "revalidated" in decision.reason
    state = _state(state_path)
    assert state["status"] == "COMPLETE"
    assert state["last_completed_step"] == 20
    assert state["last_result"] == "PASS"


def test_complete_modified_bound_artifact_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = _seed_complete_program(tmp_path, monkeypatch)
    report = tmp_path / "reports/production_validation/step_10.json"
    artifact = json.loads(report.read_text(encoding="utf-8"))
    artifact["mutation"] = "post-completion-change"
    _write_json(report, artifact)

    decision = pvo.apply_current_step(tmp_path, state_path)

    assert decision.passed is False
    assert decision.code == "PRIOR_STEP_NOT_COMPLETE"
    assert "ARTIFACT_HASH_MISMATCH" in decision.reason
    state = _state(state_path)
    assert state["status"] == "BLOCKED"
    assert state["block_code"] == "PRIOR_STEP_NOT_COMPLETE"


@pytest.mark.parametrize("missing_kind", ["evidence", "review", "freeze"])
def test_complete_missing_chain_material_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_kind: str,
) -> None:
    state_path = _seed_complete_program(tmp_path, monkeypatch)
    if missing_kind == "evidence":
        (tmp_path / pvo.evidence_path(10)).unlink()
    elif missing_kind == "review":
        (tmp_path / pvo.EXTRACTION_REVIEW).unlink()
    else:
        (tmp_path / pvo.EXTRACTION_FREEZE).unlink()

    decision = pvo.apply_current_step(tmp_path, state_path)

    assert decision.passed is False
    state = _state(state_path)
    assert state["status"] == "BLOCKED"
    assert state["last_result"] == "BLOCKED"
    assert state["block_code"] == decision.code


def test_complete_inconsistent_step20_chain_digest_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = _seed_complete_program(tmp_path, monkeypatch)
    report = tmp_path / "reports/production_validation/step_20.json"
    artifact = json.loads(report.read_text(encoding="utf-8"))
    artifact["steps_1_19_digest"] = "f" * 64
    _write_json(report, artifact)

    envelope_path = tmp_path / pvo.evidence_path(20)
    evidence = json.loads(envelope_path.read_text(encoding="utf-8"))
    evidence["artifact_sha256"] = pvo.sha256_file(report)
    _write_json(envelope_path, evidence)

    decision = pvo.apply_current_step(tmp_path, state_path)

    assert decision.passed is False
    assert decision.code == "RELEASE_CHAIN_DIGEST_MISMATCH"
    state = _state(state_path)
    assert state["status"] == "BLOCKED"
    assert state["block_code"] == "RELEASE_CHAIN_DIGEST_MISMATCH"
