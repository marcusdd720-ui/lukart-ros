from pathlib import Path

from knowledge.document import Document
from knowledge.fact_projection import FactProjection
from knowledge.generic_fact_extractor import GenericRegexFactExtractor
from knowledge.graph import KnowledgeGraph
from knowledge.metadata import Metadata
from knowledge.node import KnowledgeNode
from knowledge.provenance import EntityType
from knowledge.types import EdgeType, NodeType


def test_generic_extractor_is_domain_neutral_and_provenance_bound() -> None:
    text = "Sygn. akt ABC-12/34. Data 01.09.2026. Kwota 1 250,00 zł."
    facts = list(GenericRegexFactExtractor()("DOC-1", "dowolny", text))

    assert {fact.entity_type for fact in facts} == {
        EntityType.CASE_NUMBER,
        EntityType.DATE,
        EntityType.AMOUNT,
    }
    assert all(fact.source_document_id == "DOC-1" for fact in facts)
    assert all(fact.source_document_sha256 for fact in facts)
    assert all(text[fact.char_start : fact.char_end] == fact.value for fact in facts)


def test_projection_creates_deterministic_fact_node_and_contains_edge() -> None:
    path = Path("/tmp/example.md")
    document = Document(
        path=path,
        name="example.md",
        extension=".md",
        size=10,
        modified=__import__("datetime").datetime.now(),
        metadata=Metadata(document_id="DOC-1", doc_type="example"),
        content="Sygn. akt ABC-12/34.",
    )
    document.calculate_hash()

    graph = KnowledgeGraph()
    document_node = KnowledgeNode(
        id="document-node",
        type=NodeType.DOCUMENT,
        name=document.name,
        source=str(document.path),
    )
    graph.add_node(document_node)

    fact = next(
        iter(GenericRegexFactExtractor()("DOC-1", "example", document.content))
    )
    projected = FactProjection().project(graph, [document], [fact])

    assert len(projected) == 1
    node = projected[0]
    assert node.type == NodeType.FACT
    assert node.metadata["entity_type"] == EntityType.CASE_NUMBER.value
    assert graph.has_edge_typed(document_node.id, node.id, EdgeType.CONTAINS)

    second_graph = KnowledgeGraph(nodes=dict(graph.nodes), edges=list(graph.edges))
    projected_again = FactProjection().project(second_graph, [document], [fact])
    assert projected_again[0].id == node.id
