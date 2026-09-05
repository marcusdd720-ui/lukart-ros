"""Fail-closed validation for Step 16/18 review evidence.

Independent mode requires authenticated external-human provenance. SOLO_MAINTAINER_MODE
is a distinct, explicit certification profile and must record that no independent external
review was performed; it never upgrades maintainer acceptance into independent review.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from validation.certification_mode import (
    CertificationMode,
    CertificationProfileError,
    load_certification_profile,
)
from validation.human_review_provenance import (
    HumanReviewProvenanceError,
    validate_runtime_human_review_provenance,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_AUTOMATION_ID_RE = re.compile(
    r"(?:^|[-_.\[\]])(?:bot|factory|system|automated|automation|agent|github-actions)"
    r"(?:$|[-_.\[\]])",
    re.IGNORECASE,
)


class IndependentStepReviewError(ValueError):
    """Stable fail-closed error for Step 16/18 review validation."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True, slots=True)
class IndependentStepReview:
    step: int
    reviewed_sha: str
    reviewed_artifact_path: str
    reviewed_artifact_sha256: str
    reviewer_id: str
    reviewer_kind: str
    reviewer_independent: bool
    certification_mode: str
    review_summary: str


def _required_text(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            f"review field {name} must be non-empty text",
        )
    return value.strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "step review artifact must be valid UTF-8 JSON",
        ) from exc
    if not isinstance(value, dict):
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "step review artifact must be a JSON object",
        )
    return value


def _safe_repo_path(
    root: Path,
    raw_path: object,
    *,
    missing_code: str,
    invalid_code: str,
    label: str,
) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise IndependentStepReviewError(missing_code, f"{label} must be explicitly bound")
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise IndependentStepReviewError(
            invalid_code,
            f"{label} must be repository-relative and cannot escape the repository",
        )
    root_resolved = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise IndependentStepReviewError(
            invalid_code,
            f"{label} escapes the repository",
        ) from exc
    if not resolved.is_file():
        raise IndependentStepReviewError(missing_code, f"bound {label} is missing")
    return resolved


def _safe_review_path(root: Path, raw_path: object) -> Path:
    resolved = _safe_repo_path(
        root,
        raw_path,
        missing_code="INDEPENDENT_REVIEW_REQUIRED",
        invalid_code="REVIEW_PATH_INVALID",
        label="review_path",
    )
    if resolved.suffix.lower() != ".json":
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "step review artifact must be JSON",
        )
    return resolved


def _safe_subject_path(root: Path, raw_path: object) -> Path:
    resolved = _safe_repo_path(
        root,
        raw_path,
        missing_code="REVIEW_SUBJECT_REQUIRED",
        invalid_code="REVIEW_SUBJECT_PATH_INVALID",
        label="review_subject_path",
    )
    if resolved.suffix.lower() != ".json":
        raise IndependentStepReviewError(
            "REVIEW_SUBJECT_FORMAT_INVALID",
            "review subject must be a JSON review-package manifest",
        )
    return resolved


def _reviewer_is_automation(reviewer_id: str, reserved_reviewer_ids: frozenset[str]) -> bool:
    normalized = reviewer_id.strip().lower()
    return (
        normalized in {item.lower() for item in reserved_reviewer_ids}
        or normalized.endswith("[bot]")
        or _AUTOMATION_ID_RE.search(normalized) is not None
    )


def _certification_mode(root: Path, review: Mapping[str, object]) -> CertificationMode:
    raw_mode = review.get("review_mode")
    if raw_mode is None:
        return CertificationMode.INDEPENDENT
    if raw_mode != CertificationMode.SOLO_MAINTAINER.value:
        raise IndependentStepReviewError(
            "CERTIFICATION_MODE_INVALID",
            "review_mode must be omitted for independent review or equal solo_maintainer",
        )
    try:
        profile = load_certification_profile(root, required=True)
    except CertificationProfileError as exc:
        raise IndependentStepReviewError("CERTIFICATION_MODE_INVALID", str(exc)) from exc
    if profile.mode is not CertificationMode.SOLO_MAINTAINER:
        raise IndependentStepReviewError(
            "CERTIFICATION_MODE_INVALID",
            "solo-maintainer review requires repository mode solo_maintainer",
        )
    return profile.mode


def validate_independent_step_review(
    root: Path,
    evidence: Mapping[str, object],
    *,
    expected_step: int,
    expected_validated_sha: str,
    expected_artifact_path: str,
    expected_artifact_sha256: str,
    reserved_reviewer_ids: frozenset[str],
) -> IndependentStepReview:
    """Validate Step 16/18 review bytes under the selected certification profile."""

    if expected_step not in {16, 18}:
        raise IndependentStepReviewError(
            "REVIEW_SCOPE_INVALID",
            "step review contract is restricted to Steps 16 and 18",
        )
    if not _GIT_SHA_RE.fullmatch(expected_validated_sha):
        raise IndependentStepReviewError(
            "REVIEW_SHA_MISMATCH",
            "expected validated SHA is malformed",
        )
    if not _SHA256_RE.fullmatch(expected_artifact_sha256):
        raise IndependentStepReviewError(
            "REVIEW_ARTIFACT_MISMATCH",
            "expected Step report SHA-256 is malformed",
        )

    subject_path = _safe_subject_path(root, evidence.get("review_subject_path"))
    subject_relative = str(evidence["review_subject_path"])
    if subject_relative == expected_artifact_path:
        raise IndependentStepReviewError(
            "REVIEW_SUBJECT_SELF_REFERENCE",
            "review must bind to a pre-existing review subject, not the Step PASS report",
        )
    expected_subject_digest = evidence.get("review_subject_sha256")
    if not isinstance(expected_subject_digest, str) or not _SHA256_RE.fullmatch(
        expected_subject_digest
    ):
        raise IndependentStepReviewError(
            "REVIEW_SUBJECT_HASH_INVALID",
            "review_subject_sha256 must be an explicit SHA-256 digest",
        )
    if _sha256_file(subject_path) != expected_subject_digest:
        raise IndependentStepReviewError(
            "REVIEW_SUBJECT_HASH_MISMATCH",
            "step evidence is not bound to the exact review-subject bytes",
        )

    review_file = _safe_review_path(root, evidence.get("review_path"))
    expected_review_digest = evidence.get("review_sha256")
    if not isinstance(expected_review_digest, str) or not _SHA256_RE.fullmatch(
        expected_review_digest
    ):
        raise IndependentStepReviewError(
            "REVIEW_HASH_INVALID",
            "review_sha256 must be an explicit SHA-256 digest",
        )
    if _sha256_file(review_file) != expected_review_digest:
        raise IndependentStepReviewError(
            "REVIEW_HASH_MISMATCH",
            "step evidence is not bound to the review bytes",
        )

    review = _load_json(review_file)
    if review.get("schema_version") != "1.0":
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "step review schema_version must be 1.0",
        )
    if review.get("step") != expected_step:
        raise IndependentStepReviewError(
            "REVIEW_SCOPE_INVALID",
            "review is bound to a different Production Validation step",
        )

    reviewed_sha = _required_text(review, "reviewed_sha").lower()
    if not _GIT_SHA_RE.fullmatch(reviewed_sha) or reviewed_sha != expected_validated_sha:
        raise IndependentStepReviewError(
            "REVIEW_SHA_MISMATCH",
            "review is not bound to the validated revision",
        )

    reviewed_artifact_path = _required_text(review, "reviewed_artifact_path")
    reviewed_artifact_sha256 = _required_text(review, "reviewed_artifact_sha256").lower()
    if (
        reviewed_artifact_path != subject_relative
        or not _SHA256_RE.fullmatch(reviewed_artifact_sha256)
        or reviewed_artifact_sha256 != expected_subject_digest
    ):
        raise IndependentStepReviewError(
            "REVIEW_ARTIFACT_MISMATCH",
            "review is not bound to the declared review subject",
        )

    reviewer_id = _required_text(review, "reviewer_id")
    reviewer_kind = _required_text(review, "reviewer_kind")
    reviewer_independent = review.get("reviewer_independent")
    mode = _certification_mode(root, review)

    if mode is CertificationMode.INDEPENDENT:
        if reviewer_independent is not True or reviewer_kind != "human":
            raise IndependentStepReviewError(
                "REVIEW_NOT_INDEPENDENT",
                "review must explicitly identify an independent human reviewer",
            )
        if _reviewer_is_automation(reviewer_id, reserved_reviewer_ids):
            raise IndependentStepReviewError(
                "REVIEW_NOT_INDEPENDENT",
                "bot, agent, system, automation, or Factory identities cannot approve this gate",
            )
    else:
        try:
            profile = load_certification_profile(root, required=True)
        except CertificationProfileError as exc:
            raise IndependentStepReviewError("CERTIFICATION_MODE_INVALID", str(exc)) from exc
        if (
            reviewer_id != profile.maintainer_id
            or reviewer_kind != "maintainer"
            or reviewer_independent is not False
            or review.get("independent_external_review") != "NOT_PERFORMED"
        ):
            raise IndependentStepReviewError(
                "SOLO_MAINTAINER_ATTESTATION_INVALID",
                "solo mode requires repository maintainer identity, reviewer_independent=false, "
                "and independent_external_review=NOT_PERFORMED",
            )

    if review.get("decision") != "PASS":
        raise IndependentStepReviewError(
            "REVIEW_NOT_APPROVED",
            "step review has not recorded a PASS decision",
        )
    review_summary = _required_text(review, "review_summary")

    if mode is CertificationMode.INDEPENDENT:
        try:
            validate_runtime_human_review_provenance(
                step=expected_step,
                reviewer_id=reviewer_id,
                review_sha256=expected_review_digest,
                reviewed_sha=reviewed_sha,
            )
        except HumanReviewProvenanceError as exc:
            raise IndependentStepReviewError(exc.code, exc.reason) from exc

    return IndependentStepReview(
        step=expected_step,
        reviewed_sha=reviewed_sha,
        reviewed_artifact_path=reviewed_artifact_path,
        reviewed_artifact_sha256=reviewed_artifact_sha256,
        reviewer_id=reviewer_id,
        reviewer_kind=reviewer_kind,
        reviewer_independent=reviewer_independent is True,
        certification_mode=mode.value,
        review_summary=review_summary,
    )
