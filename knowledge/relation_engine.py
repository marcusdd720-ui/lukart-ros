"""
Knowledge Operating System (KOS)

File: knowledge/relation_engine.py
Version: 2.0
Sprint: F-012
Status: Stable
"""

from __future__ import annotations

import re

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.relation import Relation
from knowledge.relation_types import RelationType


class RelationEngine:
    """Builds logical relations between graph nodes."""

    DOCUMENT_PATTERN = re.compile(r"\b(?:ADR-\d{4}|KCS-\d+(?:\.\d+)?)\b")

    def run(self, graph: KnowledgeGraph):

        relations = []

        lookup = {}

        for node in graph.nodes.values():
            document = getattr(node, "document", None)

            if document is None:
                continue

            lookup[document.name] = node

            metadata = getattr(document, "metadata", None)

            if metadata:
                document_id = getattr(
                    metadata,
                    "document_id",
                    "",
                )

                if document_id:
                    lookup[document_id] = node

        for node in graph.nodes.values():
            document = getattr(node, "document", None)

            if document is None:
                continue

            matches = self.DOCUMENT_PATTERN.findall(document.content)

            for reference in sorted(set(matches)):
                target = lookup.get(reference)

                if target is None:
                    continue

                if target.id == node.id:
                    continue

                relation = Relation(
                    source=node.id,
                    target=target.id,
                    relation_type=RelationType.REFERENCES,
                    evidence=reference,
                )

                relations.append(relation)

                graph.add_edge(
                    KnowledgeEdge(
                        source=relation.source,
                        target=relation.target,
                    )
                )

        return relations
