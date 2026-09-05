"""Immutable KMS-1.0 projection over an authorized KCS CaseScope."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.epistemic import KnowledgeStatus
from knowledge.models.case_scope import CaseScope, ReferenceAuthorization


class TemporalView(StrEnum):
    CURRENT_KNOWLEDGE = "current_knowledge"
    KNOWLEDGE_TIME = "knowledge_time"
    EVENT_TIME = "event_time"
    SOURCE_TIME = "source_time"


@dataclass(frozen=True, slots=True)
class ProjectedCognitiveRef:
    object_id: str
    object_version: str
    case_reference_id: str
    epistemic_status: KnowledgeStatus
    provenance_refs: tuple[str, ...] = ()
    valid_time: str | None = None
    knowledge_time: str | None = None

    def __post_init__(self) -> None:
        if not self.object_id.strip():
            raise ValueError("ProjectedCognitiveRef.object_id cannot be empty")
        if not self.object_version.strip():
            raise ValueError("ProjectedCognitiveRef.object_version cannot be empty")
        if not self.case_reference_id.strip():
            raise ValueError("ProjectedCognitiveRef.case_reference_id cannot be empty")
        if any(not ref.strip() for ref in self.provenance_refs):
            raise ValueError("provenance_refs cannot contain empty values")


@dataclass(frozen=True, slots=True)
class ProjectedRelationRef:
    relation_id: str
    relation_version: str
    source_object_id: str
    target_object_id: str
    case_reference_id: str
    epistemic_status: KnowledgeStatus
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.relation_id,
            self.relation_version,
            self.source_object_id,
            self.target_object_id,
            self.case_reference_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("ProjectedRelationRef identity fields cannot be empty")
        if any(not ref.strip() for ref in self.provenance_refs):
            raise ValueError("provenance_refs cannot contain empty values")


@dataclass(frozen=True, slots=True)
class CaseModelProjection:
    case_id: str
    scope_version: int
    object_refs: tuple[ProjectedCognitiveRef, ...]
    relation_refs: tuple[ProjectedRelationRef, ...]
    source_reference_ids: tuple[str, ...]
    temporal_view: TemporalView = TemporalView.CURRENT_KNOWLEDGE
    unresolved_items: tuple[str, ...] = ()
    version: int = 1
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("CaseModelProjection.case_id cannot be empty")
        if self.scope_version < 1 or self.version < 1:
            raise ValueError("CaseModelProjection versions must be >= 1")
        if len(self.source_reference_ids) != len(set(self.source_reference_ids)):
            raise ValueError("source_reference_ids must be unique")
        if any(not item.strip() for item in self.unresolved_items):
            raise ValueError("unresolved_items cannot contain empty values")

    @classmethod
    def build(
        cls,
        scope: CaseScope,
        *,
        object_refs: tuple[ProjectedCognitiveRef, ...] = (),
        relation_refs: tuple[ProjectedRelationRef, ...] = (),
        temporal_view: TemporalView = TemporalView.CURRENT_KNOWLEDGE,
        unresolved_items: tuple[str, ...] = (),
        version: int = 1,
        lineage: tuple[str, ...] = (),
    ) -> CaseModelProjection:
        authorized = {
            reference.reference_id
            for reference in scope.reference_set.references
            if reference.authorization is ReferenceAuthorization.AUTHORIZED
        }

        object_reference_ids = {item.case_reference_id for item in object_refs}
        relation_reference_ids = {item.case_reference_id for item in relation_refs}
        used_reference_ids = object_reference_ids | relation_reference_ids
        unauthorized = used_reference_ids - authorized
        if unauthorized:
            rendered = ", ".join(sorted(unauthorized))
            raise ValueError(f"Case Model contains unauthorized references: {rendered}")

        object_ids = {item.object_id for item in object_refs}
        for relation in relation_refs:
            missing_endpoints = {
                relation.source_object_id,
                relation.target_object_id,
            } - object_ids
            if missing_endpoints:
                rendered = ", ".join(sorted(missing_endpoints))
                raise ValueError(f"relation endpoints are outside Case Model: {rendered}")

        return cls(
            case_id=scope.case_id,
            scope_version=scope.version,
            object_refs=object_refs,
            relation_refs=relation_refs,
            source_reference_ids=tuple(sorted(used_reference_ids)),
            temporal_view=temporal_view,
            unresolved_items=unresolved_items,
            version=version,
            lineage=lineage,
        )
