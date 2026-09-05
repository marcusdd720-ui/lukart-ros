"""KDOC-1.0 binding contract for dumb, traceable document rendering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_type: str
    artifact_id: str
    version: int
    digest: str

    def __post_init__(self) -> None:
        required = (self.artifact_type, self.artifact_id, self.digest)
        if any(not value.strip() for value in required):
            raise ValueError("ArtifactRef identity and digest cannot be empty")
        if self.version < 1:
            raise ValueError("ArtifactRef version must be >= 1")


@dataclass(frozen=True, slots=True)
class DocumentBinding:
    document_id: str
    renderer_id: str
    renderer_version: str
    template_id: str
    template_version: str
    input_refs: tuple[ArtifactRef, ...]
    source_digest: str
    generated_at: str
    communication_target: str
    required_sections: tuple[str, ...] = ()
    unresolved_refs: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    approval_required: bool = False
    approval_ref: str | None = None
    status: DocumentStatus = DocumentStatus.DRAFT
    version: int = 1

    def __post_init__(self) -> None:
        required = (
            self.document_id,
            self.renderer_id,
            self.renderer_version,
            self.template_id,
            self.template_version,
            self.source_digest,
            self.generated_at,
            self.communication_target,
        )
        if any(not value.strip() for value in required):
            raise ValueError("DocumentBinding required fields cannot be empty")
        if self.version < 1:
            raise ValueError("DocumentBinding version must be >= 1")
        identities = [
            (ref.artifact_type, ref.artifact_id, ref.version) for ref in self.input_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("DocumentBinding input refs must be unique")
        collections = (
            self.required_sections,
            self.unresolved_refs,
            self.contradiction_refs,
            self.limitation_refs,
        )
        if any(not value.strip() for values in collections for value in values):
            raise ValueError("DocumentBinding collections cannot contain empty values")
        if self.approval_required and self.status is DocumentStatus.APPROVED:
            if self.approval_ref is None or not self.approval_ref.strip():
                raise ValueError("APPROVED document requires recorded human approval")
        if self.approval_required and self.status is DocumentStatus.DRAFT:
            raise ValueError("high-risk document must remain REVIEW_REQUIRED until approval")

    def require_supported_sections(self, supported_sections: tuple[str, ...]) -> None:
        missing = set(self.required_sections) - set(supported_sections)
        if missing:
            raise ValueError("template requires unsupported upstream content")


@dataclass(frozen=True, slots=True)
class BoundRenderedDocument:
    binding: DocumentBinding
    media_type: str
    content: str

    def __post_init__(self) -> None:
        if not self.media_type.strip() or not self.content:
            raise ValueError("rendered document media_type/content cannot be empty")
        if self.binding.approval_required and self.binding.status is DocumentStatus.DRAFT:
            raise ValueError("high-risk rendered document cannot bypass review state")
