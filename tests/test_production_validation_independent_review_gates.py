from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.production_validation_orchestrator import evaluate_generic_evidence, evidence_path
from factory.production_validation_registry import get_program_step
from validation.human_review_provenance import PROVENANCE_DIR_ENV

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
    subject_is_report: bool = False,
) -> Path:
    if subject_is_report:
        subject_relative = str(envelope["artifact_path"])
        subject_path = report_path
    else:
        subject_relative = f"docs/quality/reviews/step_{step:02d}_review_package.json"
        subject_path = root / subject_relative
        _write_json(
            subject_path,
            {
                "schema_version": "1.0",
                "step": step,
                "validated_sha": VALIDATED_SHA,
                "purpose": "synthetic pre-existing review package for contract tests",
            },
        )
    envelope["review_subject_path"] = subject_relative
    envelope["review_subject_sha256"] = _sha256(subject_path)

    review_relative = f"docs/quality/reviews/step_{step:02d}_independent_review.json"
    review_path = root / review_relative
    _write_json(
        review_path,
        {
            "schema_version": "1.0",
            "step": step,
            "reviewed_sha": reviewed_sha,
            "reviewed_artifact_path": subject_relative,
            "reviewed_artifact_sha256": reviewed_artifact_sha256 or _sha256(subject_path),
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


def _write_step_provenance(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    step: int,
    issue: int,
    review_path: Path,
) -> None:
    review = json.loads(review_path.read_text(encoding="utf-8"))
    provenance_dir = (root / "runtime-provenance").resolve()
    provenance_dir.mkdir(parents=True, exist_ok=True)
    reviewer_id = str(review["reviewer_id"])
    _write_json(
        provenance_dir / f"step_{step:02d}.json",
        {
            "schema_version": "1.0",
            "verification_provider": "github_api",
            "source_kind": "github_issue_comment",
            "source_repository": "marcusdd720-ui/lukart-ros",
            "source_issue": issue,
            "source_comment_id": 20000 + step,
            "source_comment_url": f"https://github.com/marcusdd720-ui/lukart-ros/issues/{issue}#issuecomment-test",
            "source_author_type": "User",
            "source_author_login": reviewer_id,
            "reviewer_id": reviewer_id,
            "reviewer_kind": "human",
            "reviewer_independent": True,
            "decision": "PASS",
            "review_sha256": _sha256(review_path),
            "reviewed_sha": review["reviewed_sha"],
            "verified": True,
        },
    )
    monkeypatch.setenv(PROVENANCE_DIR_ENV, str(provenance_dir))


def test_step16_cannot_pass_from_boolean_check_without_review(tmp_path: Path) -> None:
    _prepare_step(tmp_path, 16)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.passed is False
    assert decision.code == "REVIEW_SUBJECT_REQUIRED"


def test_step18_cannot_pass_from_boolean_check_without_review(tmp_path: Path) -> None:
    _prepare_step(tmp_path, 18)

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.passed is False
    assert decision.code == "REVIEW_SUBJECT_REQUIRED"


def test_review_subject_cannot_be_the_step_pass_report(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(
        tmp_path,
        16,
        report,
        envelope_path,
        envelope,
        subject_is_report=True,
    )

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_SUBJECT_SELF_REFERENCE"


def test_review_subject_hash_must_match_exact_subject_bytes(tmp_path: Path) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 18)
    _bind_review(tmp_path, 18, report, envelope_path, envelope)
    envelope["review_subject_sha256"] = "b" * 64
    _write_json(envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.code == "REVIEW_SUBJECT_HASH_MISMATCH"


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


def test_review_must_bind_exact_review_subject_hash(tmp_path: Path) -> None:
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
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(tmp_path, 16, report, envelope_path, envelope)
    envelope["review_path"] = "../outside.json"
    _write_json(envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.code == "REVIEW_PATH_INVALID"


def test_self_declared_step16_review_without_runtime_provenance_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PROVENANCE_DIR_ENV, raising=False)
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    _bind_review(tmp_path, 16, report, envelope_path, envelope)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.passed is False
    assert decision.code == "HUMAN_PROVENANCE_REQUIRED"


def test_valid_independent_human_review_unlocks_step16_generic_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 16)
    review_path = _bind_review(tmp_path, 16, report, envelope_path, envelope)
    _write_step_provenance(tmp_path, monkeypatch, step=16, issue=62, review_path=review_path)

    decision = evaluate_generic_evidence(tmp_path, 16)

    assert decision.passed is True
    assert decision.code == "PASS"


def test_valid_independent_human_review_unlocks_step18_generic_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, envelope_path, envelope = _prepare_step(tmp_path, 18)
    review_path = _bind_review(tmp_path, 18, report, envelope_path, envelope)
    _write_step_provenance(tmp_path, monkeypatch, step=18, issue=64, review_path=review_path)

    decision = evaluate_generic_evidence(tmp_path, 18)

    assert decision.passed is True
    assert decision.code == "PASS"
