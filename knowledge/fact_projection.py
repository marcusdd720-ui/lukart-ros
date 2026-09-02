"""Projection of extracted facts into the Knowledge Graph."""

from __future__ import annotations

import hashlib

from knowledge.document import Document
from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.provenance import ExtractedFact
from knowledge.types import EdgeType, NodeType


class FactProjection:
    """Project extracted facts as deterministic FACT nodes contained by documents."""

    def project(
        self,
        graph: KnowledgeGraph,
        documents: list[Document],
        facts: list[ExtractedFact],
    ) -> list[KnowledgeNode]:
        document_nodes = self._document_nodes(graph, documents)
        projected: list[KnowledgeNode] = []

        for fact in sorted(
            facts,
            key=lambda item: (
                item.source_document_id,
                item.char_start,
                item.char_end,
                item.entity_type.value,
                item.value,
            ),
        ):
            document_node = document_nodes.get(fact.source_document_id)
            if document_node is None:
                continue

            node_id = self._fact_id(fact)
            node = KnowledgeNode(
                id=node_id,
                type=NodeType.FACT,
                name=fact.value,
                source=fact.source_document_id,
                description=fact.entity_type.value,
                metadata={
                    "entity_type": fact.entity_type.value,
                    "source_document_id": fact.source_document_id,
                    "page": fact.page,
                    "char_start": fact.char_start,
                    "char_end": fact.char_end,
                    "extractor_version": fact.extractor_version,
                    "source_document_sha256": fact.source_document_sha256,
                    "extraction_method": fact.extraction_method,
                },
            )
            graph.ensure_node(node)
            graph.ensure_edge(
                KnowledgeEdge(
                    source=document_node.id,
                    target=node_id,
                    type=EdgeType.CONTAINS,
                    description="document contains extracted fact",
                )
            )
            projected.append(graph.get_node(node_id) or node)

        return projected

    @staticmethod
    def _document_nodes(
        graph: KnowledgeGraph,
        documents: list[Document],
    ) -> dict[str, KnowledgeNode]:
        by_source = {node.source: node for node in graph.nodes.values() if node.source}
        result: dict[str, KnowledgeNode] = {}
        for document in documents:
            document_id = document.metadata.document_id
            node = by_source.get(str(document.path))
            if document_id and node is not None:
                result[document_id] = node
        return result

    @staticmethod
    def _fact_id(fact: ExtractedFact) -> str:
        payload = "|".join(
            (
                fact.source_document_id,
                fact.entity_type.value,
                fact.value,
                str(fact.page),
                str(fact.char_start),
                str(fact.char_end),
                fact.extractor_version,
                fact.source_document_sha256,
            )
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
        return f"fact-{digest}"
