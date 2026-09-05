import importlib
from dataclasses import FrozenInstanceError

import pytest

corpus_review = importlib.import_module("validation.corpus_review")
RESERVED = frozenset({"system", "automated", "factory", "lukart", "agent"})
CORPUS_SHA = "a" * 64
REVIEWED_SHA = "b" * 40
CORPUS_PATH = "data/quality/corpus_v1.json"


def _approved_review() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "corpus_id": "corpus-v1",
        "corpus_sha256": CORPUS_SHA,
        "reviewed_artifact_path": CORPUS_PATH,
        "reviewed_sha": REVIEWED_SHA,
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


def _validate(payload: dict[str, object]):
    return corpus_review.validate_external_corpus_review(
        payload,
        expected_corpus_id="corpus-v1",
        expected_corpus_sha256=CORPUS_SHA,
        reserved_reviewer_ids=RESERVED,
    )


def test_external_review_is_deterministic_and_immutable() -> None:
    first = _validate(_approved_review())
    second = _validate(_approved_review())

    assert first.digest() == second.digest()
    assert first.reviewed_artifact_path == CORPUS_PATH
    assert first.reviewed_sha == REVIEWED_SHA
    assert first.reviewer_kind == "human"
    with pytest.raises(FrozenInstanceError):
        first.reviewer_id = "changed"


def test_external_review_cannot_upgrade_rejected_decision() -> None:
    payload = _approved_review()
    payload["decision"] = "REJECTED"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_NOT_APPROVED"


def test_external_review_rejects_reserved_or_non_independent_reviewer() -> None:
    payload = _approved_review()
    payload["reviewer_id"] = "factory"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_NOT_INDEPENDENT"


def test_external_review_requires_human_reviewer_kind() -> None:
    payload = _approved_review()
    payload["reviewer_kind"] = "agent"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_NOT_INDEPENDENT"


def test_external_review_requires_exact_corpus_path() -> None:
    payload = _approved_review()
    payload["reviewed_artifact_path"] = "data/quality/other.json"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_ARTIFACT_MISMATCH"


def test_external_review_requires_full_reviewed_git_sha() -> None:
    payload = _approved_review()
    payload["reviewed_sha"] = "short-sha"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_SHA_INVALID"


def test_external_review_missing_reviewed_git_sha_fails_closed() -> None:
    payload = _approved_review()
    del payload["reviewed_sha"]

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_FORMAT_INVALID"


def test_external_review_requires_iaa_pass_when_declared() -> None:
    payload = _approved_review()
    payload["iaa_required"] = True
    payload["iaa_status"] = "FAIL"

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "IAA_REQUIRED"


def test_external_review_rejects_wrong_corpus_hash() -> None:
    payload = _approved_review()
    payload["corpus_sha256"] = "b" * 64

    with pytest.raises(corpus_review.ExternalCorpusReviewError) as exc_info:
        _validate(payload)

    assert exc_info.value.code == "REVIEW_HASH_MISMATCH"
