"""Fail-closed runtime provenance contract for independent human review gates.

Repository-authored review JSON is necessary but not sufficient. Production Validation
also requires a receipt produced outside the repository from an authenticated GitHub
issue-comment event. The receipt directory is supplied at runtime and must be absolute.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVENANCE_DIR_ENV = "LUKART_HUMAN_REVIEW_PROVENANCE_DIR"
EXPECTED_REPOSITORY = "marcusdd720-ui/lukart-ros"
GATE_ISSUES = {1: 50, 5: 51, 16: 62, 18: 64}


class HumanReviewProvenanceError(ValueError):
    """Stable fail-closed error for external reviewer provenance."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True, slots=True)
class HumanReviewProvenance:
    step: int
    reviewer_id: str
    review_sha256: str
    reviewed_sha: str
    source_issue: int
    source_comment_id: int
    source_comment_url: str


def _required_text(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            f"provenance field {name} must be non-empty text",
        )
    return value.strip()


def _receipt_path(step: int) -> Path:
    raw_dir = os.environ.get(PROVENANCE_DIR_ENV, "").strip()
    if not raw_dir:
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_REQUIRED",
            "authenticated runtime human-review provenance is missing",
        )
    directory = Path(raw_dir)
    if not directory.is_absolute():
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            "human-review provenance directory must be an absolute runtime path",
        )
    return directory / f"step_{step:02d}.json"


def _load_receipt(step: int) -> dict[str, object]:
    path = _receipt_path(step)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_REQUIRED",
            f"authenticated runtime provenance receipt is missing for Step {step}",
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            f"runtime provenance receipt is invalid for Step {step}",
        ) from exc
    if not isinstance(value, dict):
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            "runtime provenance receipt must be a JSON object",
        )
    return value


def validate_runtime_human_review_provenance(
    *,
    step: int,
    reviewer_id: str,
    review_sha256: str,
    reviewed_sha: str,
) -> HumanReviewProvenance:
    """Validate a runtime-only receipt generated from authenticated GitHub API data."""

    expected_issue = GATE_ISSUES.get(step)
    if expected_issue is None:
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_SCOPE_INVALID",
            f"Step {step} is not an external human-review gate",
        )
    if not _SHA256_RE.fullmatch(review_sha256):
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            "review_sha256 must be a SHA-256 digest",
        )
    if not _GIT_SHA_RE.fullmatch(reviewed_sha):
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            "reviewed_sha must be a full Git SHA",
        )

    receipt = _load_receipt(step)
    required = {
        "schema_version": "1.0",
        "verification_provider": "github_api",
        "source_kind": "github_issue_comment",
        "source_repository": EXPECTED_REPOSITORY,
        "source_issue": expected_issue,
        "source_author_type": "User",
        "source_author_login": reviewer_id,
        "reviewer_id": reviewer_id,
        "reviewer_kind": "human",
        "reviewer_independent": True,
        "decision": "PASS",
        "review_sha256": review_sha256,
        "reviewed_sha": reviewed_sha,
        "verified": True,
    }
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise HumanReviewProvenanceError(
                "HUMAN_PROVENANCE_MISMATCH",
                f"runtime provenance field {field} does not match the review gate",
            )

    comment_id = receipt.get("source_comment_id")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
        raise HumanReviewProvenanceError(
            "HUMAN_PROVENANCE_INVALID",
            "source_comment_id must identify an authenticated GitHub comment",
        )
    comment_url = _required_text(receipt, "source_comment_url")

    return HumanReviewProvenance(
        step=step,
        reviewer_id=reviewer_id,
        review_sha256=review_sha256,
        reviewed_sha=reviewed_sha,
        source_issue=expected_issue,
        source_comment_id=comment_id,
        source_comment_url=comment_url,
    )
