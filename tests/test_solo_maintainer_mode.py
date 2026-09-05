from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from validation.certification_mode import (
    CertificationMode,
    CertificationProfileError,
    load_certification_profile,
)
from validation.corpus_review import ExternalCorpusReviewError, validate_external_corpus_review
from validation.human_review_provenance import PROVENANCE_DIR_ENV
from validation.independent_step_review import (
    IndependentStepReviewError,
    validate_independent_step_review,
)

RESERVED = frozenset({"system", "automated", "factory", "lukart", "agent"})
OWNER = "marcusdd720-ui"


def _write_profile(root: Path, *, maintainer_id: str = OWNER) -> None:
    path = root / "factory/certification_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": "solo_maintainer",
                "maintainer_id": maintainer_id,
                "authorized_by": maintainer_id,
                "independent_external_review": "NOT_PERFORMED",
                "authorization_reason": "Explicit solo-maintainer test authorization.",
            }
        ),
        encoding="utf-8",
    )


def _corpus_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "corpus_id": "extraction-gold-v1",
        "corpus_sha256": "a" * 64,
        "reviewed_artifact_path": "data/quality/extraction_gold_v1.json",
        "reviewed_sha": "b" * 40,
        "reviewer_id": OWNER,
        "reviewer_kind": "maintainer",
        "reviewer_independent": False,
        "review_mode": "solo_maintainer",
        "independent_external_review": "NOT_PERFORMED",
        "decision": "APPROVED",
        "annotation_review": "APPROVED",
        "criticality_review": "APPROVED",
        "freeze_approved": True,
        "iaa_required": False,
        "iaa_status": "NOT_REQUIRED",
    }


def test_profile_loads_explicit_solo_mode(tmp_path: Path) -> None:
    _write_profile(tmp_path)
    profile = load_certification_profile(tmp_path, required=True)
    assert profile.mode is CertificationMode.SOLO_MAINTAINER
    assert profile.maintainer_id == OWNER
    assert profile.independent_external_review == "NOT_PERFORMED"


def test_profile_rejects_non_owner_maintainer(tmp_path: Path) -> None:
    _write_profile(tmp_path, maintainer_id="someone-else")
    with pytest.raises(CertificationProfileError):
        load_certification_profile(tmp_path, required=True)


def test_solo_corpus_acceptance_never_requires_human_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_profile(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(PROVENANCE_DIR_ENV, raising=False)
    result = validate_external_corpus_review(
        _corpus_payload(),
        expected_corpus_id="extraction-gold-v1",
        expected_corpus_sha256="a" * 64,
        reserved_reviewer_ids=RESERVED,
    )
    assert result.reviewer_id == OWNER
    assert result.reviewer_kind == "maintainer"
    assert result.reviewer_independent is False


def test_solo_corpus_rejects_false_independence_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_profile(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload = _corpus_payload()
    payload["reviewer_independent"] = True
    with pytest.raises(ExternalCorpusReviewError) as caught:
        validate_external_corpus_review(
            payload,
            expected_corpus_id="extraction-gold-v1",
            expected_corpus_sha256="a" * 64,
            reserved_reviewer_ids=RESERVED,
        )
    assert caught.value.code == "SOLO_MAINTAINER_ATTESTATION_INVALID"


def test_independent_corpus_still_requires_authenticated_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PROVENANCE_DIR_ENV, raising=False)
    payload = _corpus_payload()
    payload.pop("review_mode")
    payload.pop("independent_external_review")
    payload["reviewer_id"] = "real-reviewer"
    payload["reviewer_kind"] = "human"
    payload["reviewer_independent"] = True
    with pytest.raises(ExternalCorpusReviewError) as caught:
        validate_external_corpus_review(
            payload,
            expected_corpus_id="extraction-gold-v1",
            expected_corpus_sha256="a" * 64,
            reserved_reviewer_ids=RESERVED,
        )
    assert caught.value.code == "HUMAN_PROVENANCE_REQUIRED"


def _step_review_fixture(root: Path) -> tuple[dict[str, object], str, str]:
    _write_profile(root)
    subject_rel = "docs/quality/review_packages/step_16_review_package.json"
    subject = root / subject_rel
    subject.parent.mkdir(parents=True, exist_ok=True)
    subject.write_text('{"package":"step16"}\n', encoding="utf-8")
    subject_sha = hashlib.sha256(subject.read_bytes()).hexdigest()

    review_rel = "docs/quality/reviews/step_16_independent_review.json"
    review = root / review_rel
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "step": 16,
                "reviewed_sha": "c" * 40,
                "reviewed_artifact_path": subject_rel,
                "reviewed_artifact_sha256": subject_sha,
                "reviewer_id": OWNER,
                "reviewer_independent": False,
                "reviewer_kind": "maintainer",
                "review_mode": "solo_maintainer",
                "independent_external_review": "NOT_PERFORMED",
                "decision": "PASS",
                "review_summary": "Solo-maintainer acceptance; no independent external review.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_sha = hashlib.sha256(review.read_bytes()).hexdigest()
    evidence: dict[str, object] = {
        "review_subject_path": subject_rel,
        "review_subject_sha256": subject_sha,
        "review_path": review_rel,
        "review_sha256": review_sha,
    }
    return evidence, subject_sha, review_rel


def test_solo_step16_acceptance_is_explicitly_non_independent(tmp_path: Path) -> None:
    evidence, subject_sha, _ = _step_review_fixture(tmp_path)
    result = validate_independent_step_review(
        tmp_path,
        evidence,
        expected_step=16,
        expected_validated_sha="c" * 40,
        expected_artifact_path="reports/production_validation/step_16.json",
        expected_artifact_sha256="d" * 64,
        reserved_reviewer_ids=RESERVED,
    )
    assert result.certification_mode == "solo_maintainer"
    assert result.reviewer_kind == "maintainer"
    assert result.reviewer_independent is False
    assert result.reviewed_artifact_sha256 == subject_sha


def test_solo_step16_rejects_independence_claim(tmp_path: Path) -> None:
    evidence, _, review_rel = _step_review_fixture(tmp_path)
    review_path = tmp_path / review_rel
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["reviewer_independent"] = True
    review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    evidence["review_sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()

    with pytest.raises(IndependentStepReviewError) as caught:
        validate_independent_step_review(
            tmp_path,
            evidence,
            expected_step=16,
            expected_validated_sha="c" * 40,
            expected_artifact_path="reports/production_validation/step_16.json",
            expected_artifact_sha256="d" * 64,
            reserved_reviewer_ids=RESERVED,
        )
    assert caught.value.code == "SOLO_MAINTAINER_ATTESTATION_INVALID"
