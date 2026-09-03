"""Fail-closed validation for human review evidence on Production Validation steps.

This module validates review artifacts supplied by a real reviewer. It never creates,
infers, upgrades, or self-approves a review decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_AUTOMATION_ID_RE = re.compile(
    r"(?:^|[-_.\[\]])(?:bot|factory|system|automated|automation|agent|github-actions)"
    r"(?:$|[-_.\[\]])",
    re.IGNORECASE,
)


class IndependentStepReviewError(ValueError):
    """Stable fail-closed error for independent human review validation."""

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
            "independent review artifact must be valid UTF-8 JSON",
        ) from exc
    if not isinstance(value, dict):
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "independent review artifact must be a JSON object",
        )
    return value


def _safe_review_path(root: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise IndependentStepReviewError(
            "INDEPENDENT_REVIEW_REQUIRED",
            "step evidence must bind an independent review artifact",
        )
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise IndependentStepReviewError(
            "REVIEW_PATH_INVALID",
            "review_path must be repository-relative and cannot escape the repository",
        )
    root_resolved = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise IndependentStepReviewError(
            "REVIEW_PATH_INVALID",
            "review_path escapes the repository",
        ) from exc
    if not resolved.is_file():
        raise IndependentStepReviewError(
            "INDEPENDENT_REVIEW_REQUIRED",
            "bound independent review artifact is missing",
        )
    if resolved.suffix.lower() != ".json":
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "independent review artifact must be JSON",
        )
    return resolved


def _reviewer_is_automation(reviewer_id: str, reserved_reviewer_ids: frozenset[str]) -> bool:
    normalized = reviewer_id.strip().lower()
    return (
        normalized in {item.lower() for item in reserved_reviewer_ids}
        or normalized.endswith("[bot]")
        or _AUTOMATION_ID_RE.search(normalized) is not None
    )


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
    """Validate already supplied human review evidence for Step 16 or Step 18."""

    if expected_step not in {16, 18}:
        raise IndependentStepReviewError(
            "REVIEW_SCOPE_INVALID",
            "independent step review contract is restricted to Steps 16 and 18",
        )
    if not _GIT_SHA_RE.fullmatch(expected_validated_sha):
        raise IndependentStepReviewError(
            "REVIEW_SHA_MISMATCH",
            "expected validated SHA is malformed",
        )
    if not _SHA256_RE.fullmatch(expected_artifact_sha256):
        raise IndependentStepReviewError(
            "REVIEW_ARTIFACT_MISMATCH",
            "expected artifact SHA-256 is malformed",
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
            "step evidence is not bound to the independent review bytes",
        )

    review = _load_json(review_file)
    if review.get("schema_version") != "1.0":
        raise IndependentStepReviewError(
            "REVIEW_FORMAT_INVALID",
            "independent step review schema_version must be 1.0",
        )
    if review.get("step") != expected_step:
        raise IndependentStepReviewError(
            "REVIEW_SCOPE_INVALID",
            "independent review is bound to a different Production Validation step",
        )

    reviewed_sha = _required_text(review, "reviewed_sha").lower()
    if not _GIT_SHA_RE.fullmatch(reviewed_sha) or reviewed_sha != expected_validated_sha:
        raise IndependentStepReviewError(
            "REVIEW_SHA_MISMATCH",
            "independent review is not bound to the validated revision",
        )

    reviewed_artifact_path = _required_text(review, "reviewed_artifact_path")
    reviewed_artifact_sha256 = _required_text(review, "reviewed_artifact_sha256").lower()
    if (
        reviewed_artifact_path != expected_artifact_path
        or not _SHA256_RE.fullmatch(reviewed_artifact_sha256)
        or reviewed_artifact_sha256 != expected_artifact_sha256
    ):
        raise IndependentStepReviewError(
            "REVIEW_ARTIFACT_MISMATCH",
            "independent review is not bound to the validated report artifact",
        )

    reviewer_id = _required_text(review, "reviewer_id")
    if review.get("reviewer_independent") is not True or review.get("reviewer_kind") != "human":
        raise IndependentStepReviewError(
            "REVIEW_NOT_INDEPENDENT",
            "review must explicitly identify an independent human reviewer",
        )
    if _reviewer_is_automation(reviewer_id, reserved_reviewer_ids):
        raise IndependentStepReviewError(
            "REVIEW_NOT_INDEPENDENT",
            "bot, agent, system, automation, or Factory identities cannot approve this gate",
        )

    if review.get("decision") != "PASS":
        raise IndependentStepReviewError(
            "REVIEW_NOT_APPROVED",
            "independent human review has not recorded a PASS decision",
        )
    review_summary = _required_text(review, "review_summary")

    return IndependentStepReview(
        step=expected_step,
        reviewed_sha=reviewed_sha,
        reviewed_artifact_path=reviewed_artifact_path,
        reviewed_artifact_sha256=reviewed_artifact_sha256,
        reviewer_id=reviewer_id,
        review_summary=review_summary,
    )
