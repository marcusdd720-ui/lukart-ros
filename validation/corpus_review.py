"""Typed, immutable contract for externally supplied corpus review decisions.

This module validates review evidence; it never generates, upgrades, or infers
an approval.  External-review outcomes remain human-supplied evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CorpusReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CorpusReviewSectionStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class IAAStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PASS = "PASS"
    FAIL = "FAIL"


class ExternalCorpusReviewError(ValueError):
    """Fail-closed review validation error with stable program code."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _required_text(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExternalCorpusReviewError(
            "REVIEW_FORMAT_INVALID",
            f"review field {name} must be non-empty text",
        )
    return value.strip()


def _enum_value(enum_type: type[StrEnum], payload: Mapping[str, object], name: str) -> StrEnum:
    value = _required_text(payload, name)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ExternalCorpusReviewError(
            "REVIEW_NOT_APPROVED",
            f"review field {name} is not an accepted final review value",
        ) from exc


@dataclass(frozen=True, slots=True)
class ExternalCorpusReview:
    schema_version: str
    corpus_id: str
    corpus_sha256: str
    reviewer_id: str
    reviewer_independent: bool
    decision: CorpusReviewDecision
    annotation_review: CorpusReviewSectionStatus
    criticality_review: CorpusReviewSectionStatus
    freeze_approved: bool
    iaa_required: bool
    iaa_status: IAAStatus

    def canonical_dict(self) -> dict[str, object]:
        return {
            "annotation_review": self.annotation_review.value,
            "corpus_id": self.corpus_id,
            "corpus_sha256": self.corpus_sha256,
            "criticality_review": self.criticality_review.value,
            "decision": self.decision.value,
            "freeze_approved": self.freeze_approved,
            "iaa_required": self.iaa_required,
            "iaa_status": self.iaa_status.value,
            "reviewer_id": self.reviewer_id,
            "reviewer_independent": self.reviewer_independent,
            "schema_version": self.schema_version,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()


def validate_external_corpus_review(
    payload: Mapping[str, object],
    *,
    expected_corpus_id: str,
    expected_corpus_sha256: str,
    reserved_reviewer_ids: frozenset[str],
) -> ExternalCorpusReview:
    """Validate an already supplied independent review; never infer approval."""

    schema_version = _required_text(payload, "schema_version")
    if schema_version != "1.0":
        raise ExternalCorpusReviewError(
            "REVIEW_FORMAT_INVALID",
            "external corpus review schema_version must be 1.0",
        )

    corpus_id = _required_text(payload, "corpus_id")
    if corpus_id != expected_corpus_id:
        raise ExternalCorpusReviewError(
            "REVIEW_CORPUS_MISMATCH",
            "review corpus id mismatch",
        )

    corpus_sha256 = _required_text(payload, "corpus_sha256").lower()
    if not _SHA256_RE.fullmatch(corpus_sha256) or corpus_sha256 != expected_corpus_sha256:
        raise ExternalCorpusReviewError(
            "REVIEW_HASH_MISMATCH",
            "review is not bound to corpus bytes",
        )

    reviewer_id = _required_text(payload, "reviewer_id")
    reviewer_independent = payload.get("reviewer_independent")
    if (
        reviewer_id.lower() in reserved_reviewer_ids
        or reviewer_independent is not True
    ):
        raise ExternalCorpusReviewError(
            "REVIEW_NOT_INDEPENDENT",
            "independent reviewer required",
        )

    decision = _enum_value(CorpusReviewDecision, payload, "decision")
    annotation_review = _enum_value(
        CorpusReviewSectionStatus,
        payload,
        "annotation_review",
    )
    criticality_review = _enum_value(
        CorpusReviewSectionStatus,
        payload,
        "criticality_review",
    )
    freeze_approved = payload.get("freeze_approved")
    iaa_required = payload.get("iaa_required")
    if not isinstance(freeze_approved, bool) or not isinstance(iaa_required, bool):
        raise ExternalCorpusReviewError(
            "REVIEW_FORMAT_INVALID",
            "review freeze_approved and iaa_required fields must be boolean",
        )
    iaa_status = _enum_value(IAAStatus, payload, "iaa_status")

    if (
        decision is not CorpusReviewDecision.APPROVED
        or annotation_review is not CorpusReviewSectionStatus.APPROVED
        or criticality_review is not CorpusReviewSectionStatus.APPROVED
        or not freeze_approved
    ):
        raise ExternalCorpusReviewError(
            "REVIEW_NOT_APPROVED",
            "external review has not approved annotation, criticality, and corpus freeze",
        )
    if iaa_required and iaa_status is not IAAStatus.PASS:
        raise ExternalCorpusReviewError(
            "IAA_REQUIRED",
            "required inter-annotator agreement not passed",
        )
    if not iaa_required and iaa_status not in {IAAStatus.NOT_REQUIRED, IAAStatus.PASS}:
        raise ExternalCorpusReviewError(
            "REVIEW_NOT_APPROVED",
            "IAA status is incompatible with an approved review",
        )

    return ExternalCorpusReview(
        schema_version=schema_version,
        corpus_id=corpus_id,
        corpus_sha256=corpus_sha256,
        reviewer_id=reviewer_id,
        reviewer_independent=True,
        decision=CorpusReviewDecision(decision),
        annotation_review=CorpusReviewSectionStatus(annotation_review),
        criticality_review=CorpusReviewSectionStatus(criticality_review),
        freeze_approved=freeze_approved,
        iaa_required=iaa_required,
        iaa_status=IAAStatus(iaa_status),
    )
