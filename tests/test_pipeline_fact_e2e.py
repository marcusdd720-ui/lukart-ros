from pathlib import Path

from knowledge.generic_fact_extractor import GenericRegexFactExtractor
from knowledge.pipeline import KnowledgePipeline
from knowledge.types import EdgeType, NodeType


def test_pipeline_extracts_projects_and_validates_facts(tmp_path: Path) -> None:
    document = tmp_path / "case.md"
    document.write_text(
        "---\nid: CASE-1\ntype: decision\ntitle: Example\n---\n"
        "Sygn. akt ABC-12/34 z dnia 01.09.2026. Kwota 1250,00 zł.",
        encoding="utf-8",
    )

    pipeline = KnowledgePipeline(
        root=str(tmp_path),
        extractor=GenericRegexFactExtractor(),
    )
    graph = pipeline.run()

    fact_nodes = [node for node in graph.nodes.values() if node.type == NodeType.FACT]
    assert len(fact_nodes) == 3
    assert {node.metadata["entity_type"] for node in fact_nodes} == {
        "CASE_NUMBER",
        "DATE",
        "AMOUNT",
    }
    assert all(node.metadata["source_document_id"] == "CASE-1" for node in fact_nodes)
    assert all(
        graph.has_edge_typed(
            next(node.id for node in graph.nodes.values() if node.type == NodeType.DOCUMENT),
            node.id,
            EdgeType.CONTAINS,
        )
        for node in fact_nodes
    )
    assert graph.validate_integrity() == []
