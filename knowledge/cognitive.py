"""KMR-1.0 cognitive representation and explicit legacy graph adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from knowledge.edge import KnowledgeEdge
from knowledge.epistemic import KnowledgeStatus
from knowledge.node import KnowledgeNode
from knowledge.temporal import TemporalValue


@dataclass(frozen=True, slots=True)
class CognitiveObject:
    object_id: str
    object_type: str
    payload: Mapping[str, object]
    epistemic_state: KnowledgeStatus
    provenance_refs: tuple[str, ...]
    valid_time: TemporalValue | None
    knowledge_time: TemporalValue
    version: str
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.object_id.strip() or not self.object_type.strip() or not self.version.strip():
            raise ValueError("CognitiveObject identity/type/version cannot be empty")
        if not self.provenance_refs:
            raise ValueError("CognitiveObject requires explicit provenance")
        if any(not ref.strip() for ref in (*self.provenance_refs, *self.lineage)):
            raise ValueError("CognitiveObject references cannot contain empty values")


@dataclass(frozen=True, slots=True)
class CognitiveRelation:
    relation_id: str
    relation_type: str
    source_object_id: str
    target_object_id: str
    epistemic_state: KnowledgeStatus
    provenance_refs: tuple[str, ...]
    knowledge_time: TemporalValue
    version: str
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.relation_id,
            self.relation_type,
            self.source_object_id,
            self.target_object_id,
            self.version,
        )
        if any(not value.strip() for value in required):
            raise ValueError("CognitiveRelation identity/endpoints/version cannot be empty")
        if not self.provenance_refs:
            raise ValueError("CognitiveRelation requires explicit provenance")
        if any(not ref.strip() for ref in (*self.provenance_refs, *self.lineage)):
            raise ValueError("CognitiveRelation references cannot contain empty values")


@dataclass(frozen=True, slots=True)
class LegacyConfidenceAssessment:
    subject_id: str
    evaluator_id: str
    score: float
    provenance_ref: str

    def __post_init__(self) -> None:
        if not self.subject_id.strip() or not self.evaluator_id.strip():
            raise ValueError("LegacyConfidenceAssessment identity cannot be empty")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("LegacyConfidenceAssessment score must be between 0 and 1")
        if not self.provenance_ref.strip():
            raise ValueError("LegacyConfidenceAssessment requires provenance")


def adapt_legacy_node(
    node: KnowledgeNode,
    *,
    epistemic_state: KnowledgeStatus,
    provenance_refs: tuple[str, ...],
    knowledge_time: TemporalValue,
    version: str,
    valid_time: TemporalValue | None = None,
    lineage: tuple[str, ...] = (),
    confidence_provenance_ref: str,
) -> tuple[CognitiveObject, LegacyConfidenceAssessment]:
    """Map a legacy node without inferring epistemic state or promoting confidence."""
    node.validate()
    payload: dict[str, object] = {
        "name": node.name,
        "source": node.source,
        "description": node.description,
        "legacy_status": node.status,
        "tags": tuple(node.tags),
        "metadata": dict(node.metadata),
    }
    cognitive = CognitiveObject(
        object_id=node.id,
        object_type=str(node.type),
        payload=payload,
        epistemic_state=epistemic_state,
        provenance_refs=provenance_refs,
        valid_time=valid_time,
        knowledge_time=knowledge_time,
        version=version,
        lineage=lineage,
    )
    assessment = LegacyConfidenceAssessment(
        subject_id=node.id,
        evaluator_id="legacy-knowledge-node-confidence",
        score=node.confidence,
        provenance_ref=confidence_provenance_ref,
    )
    return cognitive, assessment


def adapt_legacy_edge(
    edge: KnowledgeEdge,
    *,
    epistemic_state: KnowledgeStatus,
    provenance_refs: tuple[str, ...],
    knowledge_time: TemporalValue,
    version: str,
    lineage: tuple[str, ...] = (),
    confidence_provenance_ref: str,
) -> tuple[CognitiveRelation, LegacyConfidenceAssessment]:
    """Map a legacy edge as its own epistemic relation without guessing truth."""
    edge.validate()
    if not edge.id.strip():
        raise ValueError("KnowledgeEdge.id must not be empty")
    relation = CognitiveRelation(
        relation_id=edge.id,
        relation_type=str(edge.type),
        source_object_id=edge.source,
        target_object_id=edge.target,
        epistemic_state=epistemic_state,
        provenance_refs=provenance_refs,
        knowledge_time=knowledge_time,
        version=version,
        lineage=lineage,
    )
    assessment = LegacyConfidenceAssessment(
        subject_id=edge.id,
        evaluator_id="legacy-knowledge-edge-confidence",
        score=edge.confidence,
        provenance_ref=confidence_provenance_ref,
    )
    return relation, assessment
