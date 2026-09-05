"""Typed, immutable contract for corpus review/acceptance decisions.

Independent mode preserves the authenticated external-human provenance contract.
SOLO_MAINTAINER_MODE is a separate, explicit profile: it never claims reviewer
independence and records that independent external review was not performed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from validation.certification_mode import (
    CertificationMode,
    CertificationProfile,
    CertificationProfileError,
    load_certification_profile,
)
from validation.human_review_provenance import (
    HumanReviewProvenanceError,
    validate_runtime_human_review_provenance,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PRODUCTION_REVIEW_STEPS = {"extraction-gold-v1": 1, "reasoning-gold-v2": 5}


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


def _canonical_corpus_path(corpus_id: str) -> str:
    """Return the canonical public corpus path for a corpus identifier."""

    return f"data/quality/{corpus_id.replace('-', '_')}.json"


@dataclass(frozen=True, slots=True)
class ExternalCorpusReview:
    schema_version: str
    corpus_id: str
    corpus_sha256: str
    reviewed_artifact_path: str
    reviewed_sha: str
    reviewer_id: str
    reviewer_kind: str
    reviewer_independent: bool
    decision: CorpusReviewDecision
    annotation_review: CorpusReviewSectionStatus
    criticality_review: CorpusReviewSectionStatus
    freeze_approved: bool
    iaa_required: bool
    iaa_status: IAAStatus

    def canonical_dict(self) -> dict[str, object]:
        # This exact field set is intentionally unchanged so independent-mode
        # authenticated provenance digests remain backwards compatible.
        return {
            "annotation_review": self.annotation_review.value,
            "corpus_id": self.corpus_id,
            "corpus_sha256": self.corpus_sha256,
            "criticality_review": self.criticality_review.value,
            "decision": self.decision.value,
            "freeze_approved": self.freeze_approved,
            "iaa_required": self.iaa_required,
            "iaa_status": self.iaa_status.value,
            "reviewed_artifact_path": self.reviewed_artifact_path,
            "reviewed_sha": self.reviewed_sha,
            "reviewer_id": self.reviewer_id,
            "reviewer_independent": self.reviewer_independent,
            "reviewer_kind": self.reviewer_kind,
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


def _profile_for_payload(payload: Mapping[str, object]) -> CertificationProfile | None:
    raw_mode = payload.get("review_mode")
    if raw_mode is None:
        return None
    if raw_mode != CertificationMode.SOLO_MAINTAINER.value:
        raise ExternalCorpusReviewError(
            "CERTIFICATION_MODE_INVALID",
            "review_mode must be omitted for independent review or equal solo_maintainer",
        )
    try:
        profile = load_certification_profile(Path.cwd(), required=True)
    except CertificationProfileError as exc:
        raise ExternalCorpusReviewError("CERTIFICATION_MODE_INVALID", str(exc)) from exc
    if profile.mode is not CertificationMode.SOLO_MAINTAINER:
        raise ExternalCorpusReviewError(
            "CERTIFICATION_MODE_INVALID",
            "solo-maintainer review requires repository mode solo_maintainer",
        )
    return profile


def _validate_reviewer_identity(
    payload: Mapping[str, object],
    *,
    reviewer_id: str,
    reviewer_kind: str,
    reviewer_independent: object,
    reserved_reviewer_ids: frozenset[str],
) -> CertificationProfile | None:
    profile = _profile_for_payload(payload)
    if profile is None:
        if (
            reviewer_id.lower() in reserved_reviewer_ids
            or reviewer_kind != "human"
            or reviewer_independent is not True
        ):
            raise ExternalCorpusReviewError(
                "REVIEW_NOT_INDEPENDENT",
                "independent human reviewer required",
            )
        return None

    if (
        reviewer_id != profile.maintainer_id
        or reviewer_kind != "maintainer"
        or reviewer_independent is not False
        or payload.get("independent_external_review") != "NOT_PERFORMED"
    ):
        raise ExternalCorpusReviewError(
            "SOLO_MAINTAINER_ATTESTATION_INVALID",
            "solo mode requires repository maintainer identity, reviewer_independent=false, "
            "and independent_external_review=NOT_PERFORMED",
        )
    return profile


def validate_external_corpus_review(
    payload: Mapping[str, object],
    *,
    expected_corpus_id: str,
    expected_corpus_sha256: str,
    reserved_reviewer_ids: frozenset[str],
) -> ExternalCorpusReview:
    """Validate independent review or explicit solo-maintainer acceptance."""

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

    reviewed_artifact_path = _required_text(payload, "reviewed_artifact_path")
    expected_artifact_path = _canonical_corpus_path(corpus_id)
    if reviewed_artifact_path != expected_artifact_path:
        raise ExternalCorpusReviewError(
            "REVIEW_ARTIFACT_MISMATCH",
            "review is not bound to the canonical corpus path",
        )

    reviewed_sha = _required_text(payload, "reviewed_sha").lower()
    if not _GIT_SHA_RE.fullmatch(reviewed_sha):
        raise ExternalCorpusReviewError(
            "REVIEW_SHA_INVALID",
            "reviewed_sha must be a full Git SHA",
        )

    reviewer_id = _required_text(payload, "reviewer_id")
    reviewer_kind = _required_text(payload, "reviewer_kind")
    reviewer_independent = payload.get("reviewer_independent")
    profile = _validate_reviewer_identity(
        payload,
        reviewer_id=reviewer_id,
        reviewer_kind=reviewer_kind,
        reviewer_independent=reviewer_independent,
        reserved_reviewer_ids=reserved_reviewer_ids,
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
            "review has not approved annotation, criticality, and corpus freeze",
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

    result = ExternalCorpusReview(
        schema_version=schema_version,
        corpus_id=corpus_id,
        corpus_sha256=corpus_sha256,
        reviewed_artifact_path=reviewed_artifact_path,
        reviewed_sha=reviewed_sha,
        reviewer_id=reviewer_id,
        reviewer_kind=reviewer_kind,
        reviewer_independent=reviewer_independent is True,
        decision=CorpusReviewDecision(decision),
        annotation_review=CorpusReviewSectionStatus(annotation_review),
        criticality_review=CorpusReviewSectionStatus(criticality_review),
        freeze_approved=freeze_approved,
        iaa_required=iaa_required,
        iaa_status=IAAStatus(iaa_status),
    )

    production_step = _PRODUCTION_REVIEW_STEPS.get(corpus_id)
    if production_step is not None and profile is None:
        try:
            validate_runtime_human_review_provenance(
                step=production_step,
                reviewer_id=reviewer_id,
                review_sha256=result.digest(),
                reviewed_sha=reviewed_sha,
            )
        except HumanReviewProvenanceError as exc:
            raise ExternalCorpusReviewError(exc.code, exc.reason) from exc

    return result
