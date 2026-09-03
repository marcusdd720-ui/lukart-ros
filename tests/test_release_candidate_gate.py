import importlib
import json
from pathlib import Path

pvo = importlib.import_module("factory.production_validation_orchestrator")
VALIDATED_SHA = "a" * 40


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _approved_review(corpus_id: str, corpus_sha256: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "corpus_id": corpus_id,
        "corpus_sha256": corpus_sha256,
        "reviewer_id": "independent-reviewer-one",
        "reviewer_independent": True,
        "decision": "APPROVED",
        "annotation_review": "APPROVED",
        "criticality_review": "APPROVED",
        "freeze_approved": True,
        "iaa_required": False,
        "iaa_status": "NOT_REQUIRED",
    }


def _artifact_for_step(step_number: int) -> dict[str, object]:
    spec = pvo.get_program_step(step_number)
    return {
        "schema_version": "1.0",
        "step": step_number,
        "status": "PASS",
        "validated_sha": VALIDATED_SHA,
        "gate_kind": spec.gate_kind.value,
        "evidence_kind": spec.evidence_kind,
        "locked_evaluation_used_for_tuning": False,
        "private_data_committed": False,
        "checks": [{"name": name, "status": "PASS"} for name in spec.required_checks],
    }


def _write_step_review(
    root: Path,
    step_number: int,
) -> tuple[str, str, str, str]:
    subject_path = Path(f"docs/quality/reviews/step_{step_number:02d}_review_package.json")
    subject = root / subject_path
    _write_json(
        subject,
        {
            "schema_version": "1.0",
            "step": step_number,
            "validated_sha": VALIDATED_SHA,
            "purpose": "synthetic pre-existing review package for release-chain tests",
        },
    )

    review_path = Path(f"docs/quality/reviews/step_{step_number:02d}_independent_review.json")
    review = root / review_path
    _write_json(
        review,
        {
            "schema_version": "1.0",
            "step": step_number,
            "reviewed_sha": VALIDATED_SHA,
            "reviewed_artifact_path": subject_path.as_posix(),
            "reviewed_artifact_sha256": pvo.sha256_file(subject),
            "reviewer_id": "external-human-reviewer",
            "reviewer_independent": True,
            "reviewer_kind": "human",
            "decision": "PASS",
            "review_summary": "Independent human fixture review for release-chain validation.",
        },
    )
    return (
        subject_path.as_posix(),
        pvo.sha256_file(subject),
        review_path.as_posix(),
        pvo.sha256_file(review),
    )


def _write_bound_evidence(
    root: Path,
    step_number: int,
    *,
    artifact: dict[str, object] | None = None,
) -> Path:
    spec = pvo.get_program_step(step_number)
    report_path = Path(f"reports/production_validation/step_{step_number:02d}.json")
    report = root / report_path
    _write_json(report, artifact or _artifact_for_step(step_number))
    envelope_payload: dict[str, object] = {
        "schema_version": "2.0",
        "step": step_number,
        "status": "PASS",
        "validated_sha": VALIDATED_SHA,
        "gate_kind": spec.gate_kind.value,
        "evidence_kind": spec.evidence_kind,
        "artifact_path": report_path.as_posix(),
        "artifact_sha256": pvo.sha256_file(report),
        "critical_gates_passed": True,
    }
    if step_number in {16, 18}:
        subject_path, subject_sha256, review_path, review_sha256 = _write_step_review(
            root,
            step_number,
        )
        envelope_payload["review_subject_path"] = subject_path
        envelope_payload["review_subject_sha256"] = subject_sha256
        envelope_payload["review_path"] = review_path
        envelope_payload["review_sha256"] = review_sha256
    envelope = root / pvo.evidence_path(step_number)
    _write_json(envelope, envelope_payload)
    return report


def _seed_reviewed_and_frozen_corpora(root: Path) -> None:
    extraction = root / pvo.EXTRACTION_CORPUS
    _write_json(extraction, {"corpus_id": "extraction-gold-v1", "items": []})
    _write_json(
        root / pvo.EXTRACTION_REVIEW,
        _approved_review("extraction-gold-v1", pvo.sha256_file(extraction)),
    )
    pvo.freeze_extraction_corpus(root)

    reasoning = root / pvo.REASONING_CORPUS_V2
    _write_json(reasoning, {"corpus_id": "reasoning-gold-v2", "cases": []})
    _write_json(
        root / pvo.REASONING_REVIEW_V2,
        _approved_review("reasoning-gold-v2", pvo.sha256_file(reasoning)),
    )
    pvo.freeze_reasoning_corpus(root)


def _seed_steps_1_through_19(root: Path) -> None:
    _seed_reviewed_and_frozen_corpora(root)
    for step_number in (*range(2, 5), *range(6, 20)):
        _write_bound_evidence(root, step_number)


def _write_release_candidate(root: Path, chain_digest: str) -> None:
    artifact = _artifact_for_step(20)
    artifact["steps_1_19_digest"] = chain_digest
    _write_bound_evidence(root, 20, artifact=artifact)


def test_release_candidate_rejects_when_external_review_is_missing(tmp_path: Path) -> None:
    extraction = tmp_path / pvo.EXTRACTION_CORPUS
    _write_json(extraction, {"corpus_id": "extraction-gold-v1"})

    decision = pvo.evaluate_release_candidate(tmp_path)

    assert decision.code == "PRIOR_STEP_NOT_COMPLETE"
    assert "step 1" in decision.reason


def test_release_candidate_rejects_stale_freeze_manifest(tmp_path: Path) -> None:
    _seed_steps_1_through_19(tmp_path)
    freeze = json.loads((tmp_path / pvo.EXTRACTION_FREEZE).read_text(encoding="utf-8"))
    freeze["reviewer_id"] = "different-reviewer"
    _write_json(tmp_path / pvo.EXTRACTION_FREEZE, freeze)

    decision = pvo.evaluate_release_candidate(tmp_path)

    assert decision.code == "FREEZE_MANIFEST_MISMATCH"


def test_release_candidate_rejects_when_prior_evidence_changes(tmp_path: Path) -> None:
    _seed_steps_1_through_19(tmp_path)
    chain_digest, chain_decision = pvo.production_validation_chain_digest(tmp_path)
    assert chain_decision is None
    assert chain_digest is not None
    _write_release_candidate(tmp_path, chain_digest)

    changed = _artifact_for_step(10)
    changed["revision"] = 2
    _write_bound_evidence(tmp_path, 10, artifact=changed)

    decision = pvo.evaluate_release_candidate(tmp_path)

    assert decision.code == "RELEASE_CHAIN_DIGEST_MISMATCH"


def test_release_candidate_accepts_exact_live_steps_1_through_19_chain(tmp_path: Path) -> None:
    _seed_steps_1_through_19(tmp_path)
    chain_digest, chain_decision = pvo.production_validation_chain_digest(tmp_path)
    assert chain_decision is None
    assert chain_digest is not None
    _write_release_candidate(tmp_path, chain_digest)

    decision = pvo.evaluate_release_candidate(tmp_path)

    assert decision.passed is True
    assert decision.code == "PASS"


def test_chain_digest_is_deterministic_for_unchanged_evidence(tmp_path: Path) -> None:
    _seed_steps_1_through_19(tmp_path)

    first, first_decision = pvo.production_validation_chain_digest(tmp_path)
    second, second_decision = pvo.production_validation_chain_digest(tmp_path)

    assert first_decision is None
    assert second_decision is None
    assert first == second
    assert first is not None
    assert (tmp_path / pvo.REASONING_FREEZE_V2).is_file()
