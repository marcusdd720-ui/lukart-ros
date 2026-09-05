from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import (
    EXTRACTION_CORPUS,
    EXTRACTION_REVIEW,
    REASONING_CORPUS_V2,
    REASONING_REVIEW_V2,
    GateDecision,
    evaluate_extraction_review,
    evaluate_generic_evidence,
    evaluate_reasoning_review,
    evidence_path,
    sha256_file,
)
from factory.production_validation_registry import PROGRAM_STEPS, get_program_step


VALIDATED_SHA = "a" * 40


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _artifact_for_step(step_number: int, validated_sha: str = VALIDATED_SHA) -> dict[str, object]:
    spec = get_program_step(step_number)
    return {
        "schema_version": "1.0",
        "step": step_number,
        "status": "PASS",
        "validated_sha": validated_sha,
        "gate_kind": spec.gate_kind.value,
        "evidence_kind": spec.evidence_kind,
        "locked_evaluation_used_for_tuning": False,
        "private_data_committed": False,
        "checks": [{"name": name, "status": "PASS"} for name in spec.required_checks],
    }


def _write_bound_evidence(
    root: Path,
    step_number: int,
    *,
    artifact: dict[str, object] | None = None,
    artifact_path: str | None = None,
    artifact_sha256: str | None = None,
    evidence_kind: str | None = None,
    critical_gates_passed: bool = True,
) -> tuple[Path, Path]:
    spec = get_program_step(step_number)
    validated_sha = VALIDATED_SHA
    report_path = artifact_path or f"reports/production_validation/step_{step_number:02d}.json"
    report = root / report_path
    if artifact_path is None or ".." not in Path(artifact_path).parts:
        _write_json(report, artifact or _artifact_for_step(step_number, validated_sha))
    digest = artifact_sha256
    if digest is None and report.is_file():
        digest = sha256_file(report)
    envelope_path = root / evidence_path(step_number)
    _write_json(
        envelope_path,
        {
            "schema_version": "2.0",
            "step": step_number,
            "status": "PASS",
            "validated_sha": validated_sha,
            "gate_kind": spec.gate_kind.value,
            "evidence_kind": evidence_kind or spec.evidence_kind,
            "artifact_path": report_path,
            "artifact_sha256": digest or "b" * 64,
            "critical_gates_passed": critical_gates_passed,
        },
    )
    return envelope_path, report


def _approved_review(corpus_id: str, corpus_sha256: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "corpus_id": corpus_id,
        "corpus_sha256": corpus_sha256,
        "reviewed_artifact_path": f"data/quality/{corpus_id.replace('-', '_')}.json",
        "reviewed_sha": VALIDATED_SHA,
        "reviewer_id": "independent-reviewer-one",
        "reviewer_kind": "human",
        "reviewer_independent": True,
        "decision": "APPROVED",
        "annotation_review": "APPROVED",
        "criticality_review": "APPROVED",
        "freeze_approved": True,
        "iaa_required": False,
        "iaa_status": "NOT_REQUIRED",
    }


def test_registry_contains_exactly_twenty_ordered_steps() -> None:
    assert len(PROGRAM_STEPS) == 20
    assert [step.number for step in PROGRAM_STEPS] == list(range(1, 21))
    assert get_program_step(20).name == "LUKART v1 Release Candidate"
    assert all(step.evidence_kind for step in PROGRAM_STEPS)


def test_extraction_review_blocks_when_artifact_is_missing(tmp_path: Path) -> None:
    _write_json(tmp_path / EXTRACTION_CORPUS, {"corpus_id": "extraction-gold-v1"})

    decision = evaluate_extraction_review(tmp_path)

    assert decision == GateDecision(
        False,
        "EXTERNAL_REVIEW_REQUIRED",
        "independent extraction corpus review artifact is missing",
    )


def test_extraction_review_rejects_reserved_reviewer(tmp_path: Path) -> None:
    corpus = tmp_path / EXTRACTION_CORPUS
    _write_json(corpus, {"corpus_id": "extraction-gold-v1"})
    review = _approved_review("extraction-gold-v1", sha256_file(corpus))
    review["reviewer_id"] = "factory"
    _write_json(tmp_path / EXTRACTION_REVIEW, review)

    decision = evaluate_extraction_review(tmp_path)

    assert decision.code == "REVIEW_NOT_INDEPENDENT"


def test_extraction_review_rejects_wrong_corpus_hash(tmp_path: Path) -> None:
    _write_json(tmp_path / EXTRACTION_CORPUS, {"corpus_id": "extraction-gold-v1"})
    _write_json(
        tmp_path / EXTRACTION_REVIEW,
        _approved_review("extraction-gold-v1", "a" * 64),
    )

    decision = evaluate_extraction_review(tmp_path)

    assert decision.code == "REVIEW_HASH_MISMATCH"


def test_extraction_review_accepts_independent_approved_review(tmp_path: Path) -> None:
    corpus = tmp_path / EXTRACTION_CORPUS
    _write_json(corpus, {"corpus_id": "extraction-gold-v1"})
    _write_json(
        tmp_path / EXTRACTION_REVIEW,
        _approved_review("extraction-gold-v1", sha256_file(corpus)),
    )

    decision = evaluate_extraction_review(tmp_path)

    assert decision.passed is True
    assert decision.code == "PASS"


def test_reasoning_review_is_bound_to_reasoning_v2_bytes(tmp_path: Path) -> None:
    corpus = tmp_path / REASONING_CORPUS_V2
    _write_json(corpus, {"corpus_id": "reasoning-gold-v2"})
    _write_json(
        tmp_path / REASONING_REVIEW_V2,
        _approved_review("reasoning-gold-v2", sha256_file(corpus)),
    )

    decision = evaluate_reasoning_review(tmp_path)

    assert decision.passed is True


def test_generic_step_requires_bound_artifact_and_required_checks(tmp_path: Path) -> None:
    _write_bound_evidence(tmp_path, 2)

    decision = evaluate_generic_evidence(tmp_path, 2)

    assert decision.passed is True


def test_generic_step_rejects_missing_critical_gate_proof(tmp_path: Path) -> None:
    _write_bound_evidence(tmp_path, 3, critical_gates_passed=False)

    decision = evaluate_generic_evidence(tmp_path, 3)

    assert decision.code == "CRITICAL_GATES_INCOMPLETE"


def test_generic_step_rejects_fabricated_artifact_digest(tmp_path: Path) -> None:
    _write_bound_evidence(tmp_path, 4, artifact_sha256="b" * 64)

    decision = evaluate_generic_evidence(tmp_path, 4)

    assert decision.code == "ARTIFACT_HASH_MISMATCH"


def test_generic_step_rejects_missing_bound_artifact(tmp_path: Path) -> None:
    spec = get_program_step(6)
    _write_json(
        tmp_path / evidence_path(6),
        {
            "schema_version": "2.0",
            "step": 6,
            "status": "PASS",
            "validated_sha": VALIDATED_SHA,
            "gate_kind": spec.gate_kind.value,
            "evidence_kind": spec.evidence_kind,
            "artifact_path": "reports/missing.json",
            "artifact_sha256": "b" * 64,
            "critical_gates_passed": True,
        },
    )

    decision = evaluate_generic_evidence(tmp_path, 6)

    assert decision.code == "ARTIFACT_REQUIRED"


def test_generic_step_rejects_path_traversal(tmp_path: Path) -> None:
    _write_bound_evidence(tmp_path, 7, artifact_path="../outside.json")

    decision = evaluate_generic_evidence(tmp_path, 7)

    assert decision.code == "ARTIFACT_PATH_INVALID"


def test_generic_step_rejects_wrong_evidence_kind(tmp_path: Path) -> None:
    _write_bound_evidence(tmp_path, 8, evidence_kind="fabricated_kind")

    decision = evaluate_generic_evidence(tmp_path, 8)

    assert decision.code == "EVIDENCE_KIND_MISMATCH"


def test_generic_step_rejects_missing_required_checks(tmp_path: Path) -> None:
    artifact = _artifact_for_step(10)
    artifact["checks"] = [{"name": "baseline_replay_recorded", "status": "PASS"}]
    _write_bound_evidence(tmp_path, 10, artifact=artifact)

    decision = evaluate_generic_evidence(tmp_path, 10)

    assert decision.code == "REQUIRED_CHECKS_MISSING"


def test_generic_step_rejects_locked_tuning_claim(tmp_path: Path) -> None:
    artifact = _artifact_for_step(12)
    artifact["locked_evaluation_used_for_tuning"] = True
    _write_bound_evidence(tmp_path, 12, artifact=artifact)

    decision = evaluate_generic_evidence(tmp_path, 12)

    assert decision.code == "ARTIFACT_CONTRACT_MISMATCH"


def test_generic_step_rejects_private_data_commit_claim(tmp_path: Path) -> None:
    artifact = _artifact_for_step(15)
    artifact["private_data_committed"] = True
    _write_bound_evidence(tmp_path, 15, artifact=artifact)

    decision = evaluate_generic_evidence(tmp_path, 15)

    assert decision.code == "ARTIFACT_CONTRACT_MISMATCH"
