from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.production_validation_orchestrator import evaluate_generic_evidence, evidence_path
from factory.production_validation_registry import get_program_step

VALIDATED_SHA = "a" * 40


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_step(root: Path, step: int) -> tuple[Path, Path, dict[str, object]]:
    spec = get_program_step(step)
    report_relative = f"reports/production_validation/step_{step:02d}.json"
    report_path = root / report_relative
    _write_json(
        report_path,
        {
            "schema_version": "1.0",
            "step": step,
            "status": "PASS",
            "validated_sha": VALIDATED_SHA,
            "gate_kind": spec.gate_kind.value,
            "evidence_kind": spec.evidence_kind,
            "locked_evaluation_used_for_tuning": False,
            "private_data_committed": False,
            "checks": [
                {"name": name, "status": "PASS"} for name in spec.required_checks
            ],
        },
    )
    envelope = {
        "schema_version": "2.0",
        "step": step,
        "status": "PASS",
        "validated_sha": VALIDATED_SHA,
        "gate_kind": spec.gate_kind.value,
        "evidence_kind": spec.evidence_kind,
        "artifact_path": report_relative,
        "artifact_sha256": _sha256(report_path),
        "critical_gates_passed": True,
    }
    envelope_path = root / evidence_path(step)
    _write_json(envelope_path, envelope)
    return report_path, envelope_path, envelope


def _bind_review(
    root: Path,
    step: int,
    report_path: Path,
    envelope_path: Path,
    envelope: dict[str, object],
    *,
    reviewer_id: str = "external-human-reviewer",
    reviewed_sha: str = VALIDATED_SHA,
    decision: str = "PASS",
    reviewed_artifact_sha256: str | None = None,
) -> Path:
    review_relative = f"docs/quality/reviews/step_{step:02d}_independent_review.json"
    review_path = root / review_relative
    _write_json(
        review_path,
        {
            "schema_version": "1.0",
            "step": step,
            "reviewed_sha": reviewed_sha,
            "reviewed_artifact_path": str(envelope["artifact_path"]),
            "reviewed_artifact_sha256": reviewed_artifact_sha256 or _sha256(report_path),
            "reviewer_id": reviewer_id,
            "reviewer_independent": True,
            "reviewer_kind": "human",
            "decision": decision,
            "review_summary": "Independent human review confirms the required gate scope.",
        },
    )
    envelope["review_path"] = review_relative
    envelope["review_sha256"] = _sha256(review_path)
    _write_json(envelope_path, envelope)
    return review_path


def test_step16_cannot_pass_from_boolean_check_without_review(tmp_path: Path) -> None:
    _prepare_step(tmp_path, 16)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.passed is False
    assert decision.code == "INDEPENDENT_REVIEW_REQUIRED"


def test_step18_cannot_pass_from_boolean_check_without_review(tmp_path: Path) -> None:
    _prepare_step(tmp_path, 18)

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.passed is False
    assert decision.code == "INDEPENDENT_REVIEW_REQUIRED"


def test_review_hash_must_match_exact_review_bytes(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(tmp_path, 16, report, envelope_path, envelope)
    envelope["review_sha256"] = "b" * 64
    _write_json(envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_HASH_MISMATCH"


def test_review_must_bind_exact_validated_sha(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(
        tmp_path,
        16,
        report,
        envelope_path,
        envelope,
        reviewed_sha="b" * 40,
    )

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_SHA_MISMATCH"


def test_review_must_bind_exact_report_hash(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 18)
    _bind_review(
        tmp_path,
        18,
        report,
        envelope_path,
        envelope,
        reviewed_artifact_sha256="b" * 64,
    )

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.code == "REVIEW_ARTIFACT_MISMATCH"


def test_factory_bot_cannot_act_as_independent_reviewer(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 18)
    _bind_review(
        tmp_path,
        18,
        report,
        envelope_path,
        envelope,
        reviewer_id="lukart-ros-factory[bot]",
    )

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.code == "REVIEW_NOT_INDEPENDENT"


def test_non_pass_human_review_blocks_gate(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(
        tmp_path,
        16,
        report,
        envelope_path,
        envelope,
        decision="FAIL",
    )

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_NOT_APPROVED"


def test_review_path_cannot_escape_repository(tmp_path: Path) -> None:
    _, envelope_path, envelope = _prepare_step(tmp_path, 16)
    envelope["review_path"] = "../outside.json"
    envelope["review_sha256"] = "b" * 64
    _write_json(envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_PATH_INVALID"


def test_valid_independent_human_review_unlocks_step16_generic_gate(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(tmp_path, 16, report, envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.passed is True
    assert decision.code == "PASS"


def test_valid_independent_human_review_unlocks_step18_generic_gate(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 18)
    _bind_review(tmp_path, 18, report, envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.passed is True
    assert decision.code == "PASS"
