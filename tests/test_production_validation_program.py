from __future__ import annotations

import json
from pathlib import Path

from factory.production_validation_orchestrator import (
    EXTRACTION_CORPUS,
    EXTRACTION_REVIEW,
    GateDecision,
    evaluate_extraction_review,
    evaluate_generic_evidence,
    evidence_path,
    sha256_file,
)
from factory.production_validation_registry import PROGRAM_STEPS, get_program_step


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_registry_contains_exactly_twenty_ordered_steps() -> None:
    assert len(PROGRAM_STEPS) == 20
    assert [step.number for step in PROGRAM_STEPS] == list(range(1, 21))
    assert get_program_step(20).name == "LUKART v1 Release Candidate"


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
    _write_json(
        tmp_path / EXTRACTION_REVIEW,
        {
            "corpus_id": "extraction-gold-v1",
            "corpus_sha256": sha256_file(corpus),
            "reviewer_id": "factory",
            "reviewer_independent": True,
            "decision": "APPROVED",
            "annotation_review": "APPROVED",
            "criticality_review": "APPROVED",
            "freeze_approved": True,
            "iaa_required": False,
        },
    )

    decision = evaluate_extraction_review(tmp_path)

    assert decision.code == "REVIEW_NOT_INDEPENDENT"


def test_extraction_review_rejects_wrong_corpus_hash(tmp_path: Path) -> None:
    _write_json(tmp_path / EXTRACTION_CORPUS, {"corpus_id": "extraction-gold-v1"})
    _write_json(
        tmp_path / EXTRACTION_REVIEW,
        {
            "corpus_id": "extraction-gold-v1",
            "corpus_sha256": "a" * 64,
            "reviewer_id": "independent-reviewer-one",
            "reviewer_independent": True,
            "decision": "APPROVED",
            "annotation_review": "APPROVED",
            "criticality_review": "APPROVED",
            "freeze_approved": True,
            "iaa_required": False,
        },
    )

    decision = evaluate_extraction_review(tmp_path)

    assert decision.code == "REVIEW_HASH_MISMATCH"


def test_extraction_review_accepts_independent_approved_review(tmp_path: Path) -> None:
    corpus = tmp_path / EXTRACTION_CORPUS
    _write_json(corpus, {"corpus_id": "extraction-gold-v1"})
    _write_json(
        tmp_path / EXTRACTION_REVIEW,
        {
            "corpus_id": "extraction-gold-v1",
            "corpus_sha256": sha256_file(corpus),
            "reviewer_id": "independent-reviewer-one",
            "reviewer_independent": True,
            "decision": "APPROVED",
            "annotation_review": "APPROVED",
            "criticality_review": "APPROVED",
            "freeze_approved": True,
            "iaa_required": False,
            "iaa_status": "NOT_REQUIRED",
        },
    )

    decision = evaluate_extraction_review(tmp_path)

    assert decision.passed is True
    assert decision.code == "PASS"


def test_generic_step_requires_exact_pass_evidence(tmp_path: Path) -> None:
    path = tmp_path / evidence_path(2)
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "step": 2,
            "status": "PASS",
            "validated_sha": "a" * 40,
            "evidence_sha256": "b" * 64,
            "critical_gates_passed": True,
        },
    )

    decision = evaluate_generic_evidence(tmp_path, 2)

    assert decision.passed is True


def test_generic_step_rejects_missing_critical_gate_proof(tmp_path: Path) -> None:
    path = tmp_path / evidence_path(3)
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "step": 3,
            "status": "PASS",
            "validated_sha": "a" * 40,
            "evidence_sha256": "b" * 64,
            "critical_gates_passed": False,
        },
    )

    decision = evaluate_generic_evidence(tmp_path, 3)

    assert decision.code == "CRITICAL_GATES_INCOMPLETE"
