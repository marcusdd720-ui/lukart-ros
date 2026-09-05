import pytest

from knowledge.cognitive import adapt_legacy_edge, adapt_legacy_node
from knowledge.edge import KnowledgeEdge
from knowledge.epistemic import KnowledgeStatus
from knowledge.node import KnowledgeNode
from knowledge.temporal import TemporalCertainty, TemporalValue
from knowledge.types import EdgeType, NodeType


def _knowledge_time() -> TemporalValue:
    return TemporalValue(
        value="2026-09-05T04:35:00Z",
        certainty=TemporalCertainty.EXACT,
        provenance_ref="prov:ingest",
    )


def test_legacy_node_requires_explicit_epistemic_state_and_keeps_confidence_derived() -> None:
    node = KnowledgeNode(
        id="NODE-1",
        type=NodeType.FACT,
        name="Synthetic fact",
        source="source:1",
        status="legacy-confirmed",
        confidence=0.82,
        metadata={"synthetic": True},
    )

    cognitive, assessment = adapt_legacy_node(
        node,
        epistemic_state=KnowledgeStatus.FACT,
        provenance_refs=("source:1",),
        knowledge_time=_knowledge_time(),
        version="v1",
        confidence_provenance_ref="legacy:node:confidence:v1",
    )

    assert cognitive.epistemic_state is KnowledgeStatus.FACT
    assert "confidence" not in cognitive.payload
    assert assessment.score == 0.82
    assert assessment.subject_id == cognitive.object_id


def test_legacy_claim_is_not_promoted_by_high_confidence() -> None:
    node = KnowledgeNode(
        id="NODE-CLAIM",
        type=NodeType.CLAIM,
        name="Synthetic claim",
        confidence=1.0,
    )

    cognitive, assessment = adapt_legacy_node(
        node,
        epistemic_state=KnowledgeStatus.CLAIM,
        provenance_refs=("source:claim",),
        knowledge_time=_knowledge_time(),
        version="v1",
        confidence_provenance_ref="legacy:claim:confidence:v1",
    )

    assert cognitive.epistemic_state is KnowledgeStatus.CLAIM
    assert assessment.score == 1.0


def test_relation_has_independent_epistemic_state_and_provenance() -> None:
    edge = KnowledgeEdge(
        id="EDGE-1",
        source="NODE-A",
        target="NODE-B",
        type=EdgeType.SUPPORTS,
        confidence=0.65,
    )

    relation, assessment = adapt_legacy_edge(
        edge,
        epistemic_state=KnowledgeStatus.CLAIM,
        provenance_refs=("source:relation",),
        knowledge_time=_knowledge_time(),
        version="v2",
        confidence_provenance_ref="legacy:edge:confidence:v1",
    )

    assert relation.source_object_id == "NODE-A"
    assert relation.target_object_id == "NODE-B"
    assert relation.epistemic_state is KnowledgeStatus.CLAIM
    assert relation.provenance_refs == ("source:relation",)
    assert assessment.score == 0.65


def test_adapter_refuses_missing_provenance() -> None:
    node = KnowledgeNode(id="NODE-1", name="Synthetic fact")

    with pytest.raises(ValueError, match="provenance"):
        adapt_legacy_node(
            node,
            epistemic_state=KnowledgeStatus.UNKNOWN,
            provenance_refs=(),
            knowledge_time=_knowledge_time(),
            version="v1",
            confidence_provenance_ref="legacy:confidence",
        )


def test_adapter_does_not_use_legacy_status_as_epistemic_authority() -> None:
    node = KnowledgeNode(
        id="NODE-1",
        name="Synthetic item",
        status="FACT",
        confidence=1.0,
    )

    cognitive, _ = adapt_legacy_node(
        node,
        epistemic_state=KnowledgeStatus.UNKNOWN,
        provenance_refs=("source:item",),
        knowledge_time=_knowledge_time(),
        version="v1",
        confidence_provenance_ref="legacy:confidence",
    )

    assert cognitive.epistemic_state is KnowledgeStatus.UNKNOWN
    assert cognitive.payload["legacy_status"] == "FACT"
