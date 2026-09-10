"""IRH-01 independent-review handoff and returned-evidence provenance contract v1.

IRH-01 converts a verified IRR-01 package into an immutable handoff identity and can
verify evidence returned by a real external reviewer. It reuses the existing Enterprise
Ed25519/CRY-01 trust-set boundary. Verification proves binding, origin and integrity of
the returned evidence; it does not manufacture reviewer independence, reviewer judgment,
certification, or any external PASS.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import cast

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
)
from core.enterprise.contracts import AttestationPurpose, SignedAttestation
from core.independent_review_readiness_v1 import (
    IRR_SCOPE_ID_V1,
    IRR_SOURCE_REPOSITORY,
    IndependentReviewReadinessError,
    verify_review_package_v1,
)
from core.p3.contracts import content_digest, require_hex_digest

IRH_HANDOFF_SCHEMA_V1 = "lukart.independent-review-handoff.v1"
IRH_REVIEWER_SCHEMA_V1 = "lukart.independent-reviewer-provenance.v1"
IRH_ARTIFACT_SCHEMA_V1 = "lukart.independent-review-artifact.v1"
IRH_STATEMENT_SCHEMA_V1 = "lukart.independent-review-statement.v1"
IRH_EVIDENCE_SCHEMA_V1 = "lukart.independent-review-evidence.v1"
IRH_VERIFICATION_SCHEMA_V1 = "lukart.independent-review-verification.v1"
IRH_SCOPE_ID_V1 = "IRH-01/v1"

IRH_EXTERNAL_REVIEW_STATUS = "AWAITING_EXTERNAL_REVIEW"
IRH_INDEPENDENT_REVIEW_STATUS = "NOT_INDEPENDENTLY_REVIEWED"
IRH_VERIFIED_EVIDENCE_STATUS = "VERIFIED_EXTERNAL_REVIEW_EVIDENCE"
IRH_INDEPENDENCE_STATUS = "REVIEWER_DECLARED_INDEPENDENCE_NOT_SYSTEM_CERTIFIED"
IRH_AUTHORITY = "external-review-evidence-verification-only-no-certification"
IRH_INDEPENDENCE_DECLARATION = "REVIEWER_DECLARED_INDEPENDENT"

MAX_REVIEW_ARTIFACT_BYTES_V1 = 32 * 1024 * 1024

_HANDOFF_KEYS = frozenset(
    {
        "schema",
        "scope_id",
        "authority",
        "source_repository",
        "irr_scope_id",
        "irr_source_commit_sha",
        "irr_package_name",
        "irr_package_sha256",
        "external_review_status",
        "independent_review_status",
        "handoff_identity",
    }
)
_REVIEWER_KEYS = frozenset(
    {
        "schema",
        "reviewer_id",
        "organization",
        "role",
        "independence_declaration",
        "provenance_identity",
    }
)
_ARTIFACT_KEYS = frozenset(
    {"schema", "name", "media_type", "sha256", "size", "artifact_identity"}
)
_STATEMENT_KEYS = frozenset(
    {
        "schema",
        "handoff",
        "reviewer",
        "artifact",
        "outcome",
        "review_completed_at",
        "statement_identity",
    }
)
_EVIDENCE_KEYS = frozenset(
    {"schema", "statement", "attestation", "evidence_bundle_identity"}
)
_ATTESTATION_KEYS = frozenset(
    {
        "key_id",
        "purpose",
        "subject_digest",
        "payload_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "signature_b64",
    }
)


class IndependentReviewHandoffError(ValueError):
    """Fail-closed IRH-01 handoff/evidence contract violation."""


class ReviewerOutcomeV1(StrEnum):
    PASS = "PASS"
    PASS_WITH_FINDINGS = "PASS_WITH_FINDINGS"
    FAIL = "FAIL"
    ABSTAIN = "ABSTAIN"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise IndependentReviewHandoffError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _nonnegative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise IndependentReviewHandoffError(
            f"{field_name} must be a nonnegative integer"
        )
    return value


def _hex_digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(_text(value, field_name=field_name), field_name=field_name)
    except ValueError as exc:
        raise IndependentReviewHandoffError(str(exc)) from exc


def _git_sha(value: object, *, field_name: str) -> str:
    normalized = _text(value, field_name=field_name)
    if len(normalized) != 40 or any(ch not in "abcdef01234" "56789" for ch in normalized):
        raise IndependentReviewHandoffError(
            f"{field_name} must be a lowercase 40-character Git SHA"
        )
    return normalized


def _strict_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual))
    unknown = ",".join(sorted(actual - expected))
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if unknown:
        details.append(f"unknown={unknown}")
    raise IndependentReviewHandoffError(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


def _safe_filename(value: object, *, field_name: str) -> str:
    name = _text(value, field_name=field_name)
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.name != name
        or name in {".", ".."}
        or "\\" in name
    ):
        raise IndependentReviewHandoffError(f"{field_name} must be a safe basename")
    return name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_object(path: Path, *, field_name: str) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentReviewHandoffError(f"invalid {field_name} JSON") from exc
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise IndependentReviewHandoffError(f"{field_name} must be a JSON object")
    return cast(dict[str, object], raw)


def _attestation_dict(attestation: SignedAttestation) -> dict[str, object]:
    return {
        "key_id": attestation.key_id,
        "purpose": attestation.purpose.value,
        "subject_digest": attestation.subject_digest,
        "payload_digest": attestation.payload_digest,
        "issued_at": attestation.issued_at,
        "expires_at": attestation.expires_at,
        "nonce": attestation.nonce,
        "signature_b64": attestation.signature_b64,
    }


def _attestation_from_dict(value: Mapping[str, object]) -> SignedAttestation:
    _strict_keys(value, _ATTESTATION_KEYS, field_name="attestation")
    try:
        purpose = AttestationPurpose(
            _text(value.get("purpose"), field_name="attestation purpose")
        )
    except ValueError as exc:
        raise IndependentReviewHandoffError("unknown attestation purpose") from exc
    issued_at = _nonnegative_int(value.get("issued_at"), field_name="attestation issued_at")
    expires_raw = value.get("expires_at")
    expires_at = (
        None
        if expires_raw is None
        else _nonnegative_int(expires_raw, field_name="attestation expires_at")
    )
    return SignedAttestation(
        key_id=_text(value.get("key_id"), field_name="attestation key_id"),
        purpose=purpose,
        subject_digest=_hex_digest(
            value.get("subject_digest"), field_name="attestation subject_digest"
        ),
        payload_digest=_hex_digest(
            value.get("payload_digest"), field_name="attestation payload_digest"
        ),
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=_text(value.get("nonce"), field_name="attestation nonce"),
        signature_b64=_text(
            value.get("signature_b64"), field_name="attestation signature_b64"
        ),
    )


@dataclass(frozen=True, slots=True)
class IndependentReviewHandoffV1:
    irr_source_commit_sha: str
    irr_package_name: str
    irr_package_sha256: str
    handoff_identity: str
    schema: str = IRH_HANDOFF_SCHEMA_V1
    scope_id: str = IRH_SCOPE_ID_V1
    authority: str = IRH_AUTHORITY
    source_repository: str = IRR_SOURCE_REPOSITORY
    irr_scope_id: str = IRR_SCOPE_ID_V1
    external_review_status: str = IRH_EXTERNAL_REVIEW_STATUS
    independent_review_status: str = IRH_INDEPENDENT_REVIEW_STATUS

    def __post_init__(self) -> None:
        if self.schema != IRH_HANDOFF_SCHEMA_V1:
            raise IndependentReviewHandoffError(f"unsupported handoff schema: {self.schema}")
        if self.scope_id != IRH_SCOPE_ID_V1:
            raise IndependentReviewHandoffError("handoff scope mismatch")
        if self.authority != IRH_AUTHORITY:
            raise IndependentReviewHandoffError("handoff authority mismatch")
        if self.source_repository != IRR_SOURCE_REPOSITORY:
            raise IndependentReviewHandoffError("handoff source repository mismatch")
        if self.irr_scope_id != IRR_SCOPE_ID_V1:
            raise IndependentReviewHandoffError("handoff IRR scope mismatch")
        if self.external_review_status != IRH_EXTERNAL_REVIEW_STATUS:
            raise IndependentReviewHandoffError("handoff external review status mismatch")
        if self.independent_review_status != IRH_INDEPENDENT_REVIEW_STATUS:
            raise IndependentReviewHandoffError("handoff independent review status mismatch")
        object.__setattr__(
            self,
            "irr_source_commit_sha",
            _git_sha(self.irr_source_commit_sha, field_name="irr_source_commit_sha"),
        )
        object.__setattr__(
            self,
            "irr_package_name",
            _safe_filename(self.irr_package_name, field_name="irr_package_name"),
        )
        object.__setattr__(
            self,
            "irr_package_sha256",
            _hex_digest(self.irr_package_sha256, field_name="irr_package_sha256"),
        )
        object.__setattr__(
            self,
            "handoff_identity",
            _hex_digest(self.handoff_identity, field_name="handoff_identity"),
        )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        irr_source_commit_sha: str,
        irr_package_name: str,
        irr_package_sha256: str,
    ) -> IndependentReviewHandoffV1:
        body = cls._body(
            irr_source_commit_sha=_git_sha(
                irr_source_commit_sha, field_name="irr_source_commit_sha"
            ),
            irr_package_name=_safe_filename(
                irr_package_name, field_name="irr_package_name"
            ),
            irr_package_sha256=_hex_digest(
                irr_package_sha256, field_name="irr_package_sha256"
            ),
        )
        return cls(
            irr_source_commit_sha=cast(str, body["irr_source_commit_sha"]),
            irr_package_name=cast(str, body["irr_package_name"]),
            irr_package_sha256=cast(str, body["irr_package_sha256"]),
            handoff_identity=content_digest(body),
        )

    @staticmethod
    def _body(
        *,
        irr_source_commit_sha: str,
        irr_package_name: str,
        irr_package_sha256: str,
    ) -> dict[str, object]:
        return {
            "schema": IRH_HANDOFF_SCHEMA_V1,
            "scope_id": IRH_SCOPE_ID_V1,
            "authority": IRH_AUTHORITY,
            "source_repository": IRR_SOURCE_REPOSITORY,
            "irr_scope_id": IRR_SCOPE_ID_V1,
            "irr_source_commit_sha": irr_source_commit_sha,
            "irr_package_name": irr_package_name,
            "irr_package_sha256": irr_package_sha256,
            "external_review_status": IRH_EXTERNAL_REVIEW_STATUS,
            "independent_review_status": IRH_INDEPENDENT_REVIEW_STATUS,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> IndependentReviewHandoffV1:
        _strict_keys(value, _HANDOFF_KEYS, field_name="handoff")
        candidate = cls(
            irr_source_commit_sha=_git_sha(
                value.get("irr_source_commit_sha"), field_name="irr_source_commit_sha"
            ),
            irr_package_name=_safe_filename(
                value.get("irr_package_name"), field_name="irr_package_name"
            ),
            irr_package_sha256=_hex_digest(
                value.get("irr_package_sha256"), field_name="irr_package_sha256"
            ),
            handoff_identity=_hex_digest(
                value.get("handoff_identity"), field_name="handoff_identity"
            ),
            schema=_text(value.get("schema"), field_name="handoff schema"),
            scope_id=_text(value.get("scope_id"), field_name="handoff scope_id"),
            authority=_text(value.get("authority"), field_name="handoff authority"),
            source_repository=_text(
                value.get("source_repository"), field_name="source_repository"
            ),
            irr_scope_id=_text(value.get("irr_scope_id"), field_name="irr_scope_id"),
            external_review_status=_text(
                value.get("external_review_status"),
                field_name="external_review_status",
            ),
            independent_review_status=_text(
                value.get("independent_review_status"),
                field_name="independent_review_status",
            ),
        )
        if candidate.canonical_dict() != dict(value):
            raise IndependentReviewHandoffError("handoff is not canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            irr_source_commit_sha=self.irr_source_commit_sha,
            irr_package_name=self.irr_package_name,
            irr_package_sha256=self.irr_package_sha256,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "handoff_identity": self.handoff_identity}

    def verify_identity(self) -> None:
        if self.handoff_identity != content_digest(self.canonical_body()):
            raise IndependentReviewHandoffError("handoff content-address mismatch")


@dataclass(frozen=True, slots=True)
class ReviewerProvenanceV1:
    reviewer_id: str
    organization: str
    role: str
    independence_declaration: str
    provenance_identity: str
    schema: str = IRH_REVIEWER_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != IRH_REVIEWER_SCHEMA_V1:
            raise IndependentReviewHandoffError(
                f"unsupported reviewer provenance schema: {self.schema}"
            )
        for field_name in ("reviewer_id", "organization", "role"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name=field_name),
            )
        if self.independence_declaration != IRH_INDEPENDENCE_DECLARATION:
            raise IndependentReviewHandoffError(
                "reviewer independence must be explicitly declared"
            )
        object.__setattr__(
            self,
            "provenance_identity",
            _hex_digest(self.provenance_identity, field_name="provenance_identity"),
        )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        reviewer_id: str,
        organization: str,
        role: str,
    ) -> ReviewerProvenanceV1:
        body = cls._body(
            reviewer_id=_text(reviewer_id, field_name="reviewer_id"),
            organization=_text(organization, field_name="organization"),
            role=_text(role, field_name="role"),
        )
        return cls(
            reviewer_id=cast(str, body["reviewer_id"]),
            organization=cast(str, body["organization"]),
            role=cast(str, body["role"]),
            independence_declaration=IRH_INDEPENDENCE_DECLARATION,
            provenance_identity=content_digest(body),
        )

    @staticmethod
    def _body(*, reviewer_id: str, organization: str, role: str) -> dict[str, object]:
        return {
            "schema": IRH_REVIEWER_SCHEMA_V1,
            "reviewer_id": reviewer_id,
            "organization": organization,
            "role": role,
            "independence_declaration": IRH_INDEPENDENCE_DECLARATION,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReviewerProvenanceV1:
        _strict_keys(value, _REVIEWER_KEYS, field_name="reviewer provenance")
        candidate = cls(
            reviewer_id=_text(value.get("reviewer_id"), field_name="reviewer_id"),
            organization=_text(value.get("organization"), field_name="organization"),
            role=_text(value.get("role"), field_name="role"),
            independence_declaration=_text(
                value.get("independence_declaration"),
                field_name="independence_declaration",
            ),
            provenance_identity=_hex_digest(
                value.get("provenance_identity"), field_name="provenance_identity"
            ),
            schema=_text(value.get("schema"), field_name="reviewer provenance schema"),
        )
        if candidate.canonical_dict() != dict(value):
            raise IndependentReviewHandoffError("reviewer provenance is not canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            reviewer_id=self.reviewer_id,
            organization=self.organization,
            role=self.role,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "provenance_identity": self.provenance_identity}

    def verify_identity(self) -> None:
        if self.provenance_identity != content_digest(self.canonical_body()):
            raise IndependentReviewHandoffError(
                "reviewer provenance content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ReviewArtifactIdentityV1:
    name: str
    media_type: str
    sha256: str
    size: int
    artifact_identity: str
    schema: str = IRH_ARTIFACT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != IRH_ARTIFACT_SCHEMA_V1:
            raise IndependentReviewHandoffError(
                f"unsupported review artifact schema: {self.schema}"
            )
        object.__setattr__(self, "name", _safe_filename(self.name, field_name="artifact name"))
        object.__setattr__(
            self, "media_type", _text(self.media_type, field_name="artifact media_type")
        )
        object.__setattr__(self, "sha256", _hex_digest(self.sha256, field_name="artifact sha256"))
        size = _nonnegative_int(self.size, field_name="artifact size")
        if size > MAX_REVIEW_ARTIFACT_BYTES_V1:
            raise IndependentReviewHandoffError("review artifact exceeds size limit")
        object.__setattr__(self, "size", size)
        object.__setattr__(
            self,
            "artifact_identity",
            _hex_digest(self.artifact_identity, field_name="artifact_identity"),
        )
        self.verify_identity()

    @classmethod
    def for_bytes(
        cls,
        *,
        name: str,
        media_type: str,
        data: bytes,
    ) -> ReviewArtifactIdentityV1:
        if len(data) > MAX_REVIEW_ARTIFACT_BYTES_V1:
            raise IndependentReviewHandoffError("review artifact exceeds size limit")
        safe_name = _safe_filename(name, field_name="artifact name")
        canonical_media_type = _text(media_type, field_name="artifact media_type")
        body = cls._body(
            name=safe_name,
            media_type=canonical_media_type,
            sha256=_sha256(data),
            size=len(data),
        )
        return cls(
            name=safe_name,
            media_type=canonical_media_type,
            sha256=cast(str, body["sha256"]),
            size=len(data),
            artifact_identity=content_digest(body),
        )

    @staticmethod
    def _body(
        *,
        name: str,
        media_type: str,
        sha256: str,
        size: int,
    ) -> dict[str, object]:
        return {
            "schema": IRH_ARTIFACT_SCHEMA_V1,
            "name": name,
            "media_type": media_type,
            "sha256": sha256,
            "size": size,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReviewArtifactIdentityV1:
        _strict_keys(value, _ARTIFACT_KEYS, field_name="review artifact")
        candidate = cls(
            name=_safe_filename(value.get("name"), field_name="artifact name"),
            media_type=_text(value.get("media_type"), field_name="artifact media_type"),
            sha256=_hex_digest(value.get("sha256"), field_name="artifact sha256"),
            size=_nonnegative_int(value.get("size"), field_name="artifact size"),
            artifact_identity=_hex_digest(
                value.get("artifact_identity"), field_name="artifact_identity"
            ),
            schema=_text(value.get("schema"), field_name="review artifact schema"),
        )
        if candidate.canonical_dict() != dict(value):
            raise IndependentReviewHandoffError("review artifact identity is not canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            name=self.name,
            media_type=self.media_type,
            sha256=self.sha256,
            size=self.size,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "artifact_identity": self.artifact_identity}

    def verify_identity(self) -> None:
        if self.artifact_identity != content_digest(self.canonical_body()):
            raise IndependentReviewHandoffError(
                "review artifact content-address mismatch"
            )

    def verify_bytes(self, *, name: str, data: bytes) -> None:
        if _safe_filename(name, field_name="review artifact filename") != self.name:
            raise IndependentReviewHandoffError("review artifact filename mismatch")
        if len(data) != self.size:
            raise IndependentReviewHandoffError("review artifact size mismatch")
        if _sha256(data) != self.sha256:
            raise IndependentReviewHandoffError("review artifact SHA-256 mismatch")


@dataclass(frozen=True, slots=True)
class ReviewStatementV1:
    handoff: IndependentReviewHandoffV1
    reviewer: ReviewerProvenanceV1
    artifact: ReviewArtifactIdentityV1
    outcome: ReviewerOutcomeV1
    review_completed_at: int
    statement_identity: str
    schema: str = IRH_STATEMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != IRH_STATEMENT_SCHEMA_V1:
            raise IndependentReviewHandoffError(
                f"unsupported review statement schema: {self.schema}"
            )
        if not isinstance(self.outcome, ReviewerOutcomeV1):
            raise IndependentReviewHandoffError("unknown reviewer outcome")
        object.__setattr__(
            self,
            "review_completed_at",
            _nonnegative_int(self.review_completed_at, field_name="review_completed_at"),
        )
        object.__setattr__(
            self,
            "statement_identity",
            _hex_digest(self.statement_identity, field_name="statement_identity"),
        )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        handoff: IndependentReviewHandoffV1,
        reviewer: ReviewerProvenanceV1,
        artifact: ReviewArtifactIdentityV1,
        outcome: ReviewerOutcomeV1,
        review_completed_at: int,
    ) -> ReviewStatementV1:
        completed = _nonnegative_int(
            review_completed_at, field_name="review_completed_at"
        )
        body = cls._body(
            handoff=handoff,
            reviewer=reviewer,
            artifact=artifact,
            outcome=outcome,
            review_completed_at=completed,
        )
        return cls(
            handoff=handoff,
            reviewer=reviewer,
            artifact=artifact,
            outcome=outcome,
            review_completed_at=completed,
            statement_identity=content_digest(body),
        )

    @staticmethod
    def _body(
        *,
        handoff: IndependentReviewHandoffV1,
        reviewer: ReviewerProvenanceV1,
        artifact: ReviewArtifactIdentityV1,
        outcome: ReviewerOutcomeV1,
        review_completed_at: int,
    ) -> dict[str, object]:
        return {
            "schema": IRH_STATEMENT_SCHEMA_V1,
            "handoff": handoff.canonical_dict(),
            "reviewer": reviewer.canonical_dict(),
            "artifact": artifact.canonical_dict(),
            "outcome": outcome.value,
            "review_completed_at": review_completed_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReviewStatementV1:
        _strict_keys(value, _STATEMENT_KEYS, field_name="review statement")
        handoff_raw = value.get("handoff")
        reviewer_raw = value.get("reviewer")
        artifact_raw = value.get("artifact")
        if not isinstance(handoff_raw, Mapping):
            raise IndependentReviewHandoffError("review statement handoff must be an object")
        if not isinstance(reviewer_raw, Mapping):
            raise IndependentReviewHandoffError("review statement reviewer must be an object")
        if not isinstance(artifact_raw, Mapping):
            raise IndependentReviewHandoffError("review statement artifact must be an object")
        try:
            outcome = ReviewerOutcomeV1(
                _text(value.get("outcome"), field_name="reviewer outcome")
            )
        except ValueError as exc:
            raise IndependentReviewHandoffError("unknown reviewer outcome") from exc
        candidate = cls(
            handoff=IndependentReviewHandoffV1.from_dict(handoff_raw),
            reviewer=ReviewerProvenanceV1.from_dict(reviewer_raw),
            artifact=ReviewArtifactIdentityV1.from_dict(artifact_raw),
            outcome=outcome,
            review_completed_at=_nonnegative_int(
                value.get("review_completed_at"), field_name="review_completed_at"
            ),
            statement_identity=_hex_digest(
                value.get("statement_identity"), field_name="statement_identity"
            ),
            schema=_text(value.get("schema"), field_name="review statement schema"),
        )
        if candidate.canonical_dict() != dict(value):
            raise IndependentReviewHandoffError("review statement is not canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            handoff=self.handoff,
            reviewer=self.reviewer,
            artifact=self.artifact,
            outcome=self.outcome,
            review_completed_at=self.review_completed_at,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "statement_identity": self.statement_identity}

    def verify_identity(self) -> None:
        self.handoff.verify_identity()
        self.reviewer.verify_identity()
        self.artifact.verify_identity()
        if self.statement_identity != content_digest(self.canonical_body()):
            raise IndependentReviewHandoffError(
                "review statement content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ExternalReviewEvidenceV1:
    statement: ReviewStatementV1
    attestation: SignedAttestation
    evidence_bundle_identity: str
    schema: str = IRH_EVIDENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != IRH_EVIDENCE_SCHEMA_V1:
            raise IndependentReviewHandoffError(
                f"unsupported review evidence schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "evidence_bundle_identity",
            _hex_digest(
                self.evidence_bundle_identity, field_name="evidence_bundle_identity"
            ),
        )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        statement: ReviewStatementV1,
        attestation: SignedAttestation,
    ) -> ExternalReviewEvidenceV1:
        body = cls._body(statement=statement, attestation=attestation)
        return cls(
            statement=statement,
            attestation=attestation,
            evidence_bundle_identity=content_digest(body),
        )

    @staticmethod
    def _body(
        *,
        statement: ReviewStatementV1,
        attestation: SignedAttestation,
    ) -> dict[str, object]:
        return {
            "schema": IRH_EVIDENCE_SCHEMA_V1,
            "statement": statement.canonical_dict(),
            "attestation": _attestation_dict(attestation),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ExternalReviewEvidenceV1:
        _strict_keys(value, _EVIDENCE_KEYS, field_name="review evidence")
        statement_raw = value.get("statement")
        attestation_raw = value.get("attestation")
        if not isinstance(statement_raw, Mapping):
            raise IndependentReviewHandoffError("review evidence statement must be an object")
        if not isinstance(attestation_raw, Mapping):
            raise IndependentReviewHandoffError(
                "review evidence attestation must be an object"
            )
        candidate = cls(
            statement=ReviewStatementV1.from_dict(statement_raw),
            attestation=_attestation_from_dict(attestation_raw),
            evidence_bundle_identity=_hex_digest(
                value.get("evidence_bundle_identity"),
                field_name="evidence_bundle_identity",
            ),
            schema=_text(value.get("schema"), field_name="review evidence schema"),
        )
        if candidate.canonical_dict() != dict(value):
            raise IndependentReviewHandoffError("review evidence is not canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(statement=self.statement, attestation=self.attestation)

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "evidence_bundle_identity": self.evidence_bundle_identity,
        }

    def verify_identity(self) -> None:
        self.statement.verify_identity()
        if self.evidence_bundle_identity != content_digest(self.canonical_body()):
            raise IndependentReviewHandoffError(
                "review evidence bundle content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ReviewEvidenceVerificationV1:
    evidence_bundle_identity: str
    statement_identity: str
    handoff_identity: str
    reviewer_id: str
    reviewer_declared_outcome: ReviewerOutcomeV1
    crypto_verification_digest: str
    trust_set_digest: str
    evidence_status: str = IRH_VERIFIED_EVIDENCE_STATUS
    independence_status: str = IRH_INDEPENDENCE_STATUS
    independent_review_status: str = IRH_INDEPENDENT_REVIEW_STATUS
    automation_can_certify: bool = False
    schema: str = IRH_VERIFICATION_SCHEMA_V1

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "evidence_bundle_identity": self.evidence_bundle_identity,
            "statement_identity": self.statement_identity,
            "handoff_identity": self.handoff_identity,
            "reviewer_id": self.reviewer_id,
            "reviewer_declared_outcome": self.reviewer_declared_outcome.value,
            "crypto_verification_digest": self.crypto_verification_digest,
            "trust_set_digest": self.trust_set_digest,
            "evidence_status": self.evidence_status,
            "independence_status": self.independence_status,
            "independent_review_status": self.independent_review_status,
            "automation_can_certify": self.automation_can_certify,
        }


def build_handoff_from_irr_package_v1(package_path: Path) -> IndependentReviewHandoffV1:
    """Verify IRR-01 bytes first, then bind the exact verified package into a handoff."""

    try:
        verified = verify_review_package_v1(package_path)
    except IndependentReviewReadinessError as exc:
        raise IndependentReviewHandoffError(str(exc)) from exc
    return IndependentReviewHandoffV1.build(
        irr_source_commit_sha=verified.source_commit_sha,
        irr_package_name=verified.package_path.name,
        irr_package_sha256=verified.package_sha256,
    )


def load_handoff_v1(path: Path) -> IndependentReviewHandoffV1:
    return IndependentReviewHandoffV1.from_dict(
        _json_object(path, field_name="handoff")
    )


def load_review_evidence_v1(path: Path) -> ExternalReviewEvidenceV1:
    return ExternalReviewEvidenceV1.from_dict(
        _json_object(path, field_name="review evidence")
    )


def load_trust_set_v1(path: Path) -> CryptoTrustSetV1:
    raw = _json_object(path, field_name="crypto trust set")
    try:
        return CryptoTrustSetV1.from_dict(raw)
    except CryptoAgilityV1Error as exc:
        raise IndependentReviewHandoffError(str(exc)) from exc


def verify_external_review_evidence_v1(
    *,
    expected_handoff: IndependentReviewHandoffV1,
    evidence: ExternalReviewEvidenceV1,
    review_artifact_path: Path,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    now: int,
) -> ReviewEvidenceVerificationV1:
    """Verify returned evidence without converting it into an independent/certified PASS."""

    expected_handoff.verify_identity()
    evidence.verify_identity()
    statement = evidence.statement
    if statement.handoff != expected_handoff:
        raise IndependentReviewHandoffError("review evidence handoff mismatch")
    try:
        data = review_artifact_path.read_bytes()
    except OSError as exc:
        raise IndependentReviewHandoffError("review artifact cannot be read") from exc
    statement.artifact.verify_bytes(name=review_artifact_path.name, data=data)
    if statement.reviewer.reviewer_id != evidence.attestation.key_id:
        raise IndependentReviewHandoffError(
            "reviewer identity must equal the attestation key identity"
        )
    if statement.review_completed_at > evidence.attestation.issued_at:
        raise IndependentReviewHandoffError(
            "review completion cannot be after attestation issuance"
        )
    if statement.review_completed_at > now:
        raise IndependentReviewHandoffError("review completion cannot be in the future")
    try:
        crypto = CryptoTrustVerifierV1(
            trust_set,
            expected_trust_set_digest=expected_trust_set_digest,
        ).verify(
            evidence.attestation,
            expected_purpose=AttestationPurpose.SECURITY_REVIEW,
            expected_subject_digest=statement.statement_identity,
            payload=statement.canonical_body(),
            now=now,
        )
    except CryptoAgilityV1Error as exc:
        raise IndependentReviewHandoffError(str(exc)) from exc
    return ReviewEvidenceVerificationV1(
        evidence_bundle_identity=evidence.evidence_bundle_identity,
        statement_identity=statement.statement_identity,
        handoff_identity=expected_handoff.handoff_identity,
        reviewer_id=statement.reviewer.reviewer_id,
        reviewer_declared_outcome=statement.outcome,
        crypto_verification_digest=crypto.verification_digest,
        trust_set_digest=crypto.trust_set_digest,
    )
