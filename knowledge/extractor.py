"""
Knowledge Operating System (KOS)

File: knowledge/extractor.py
Version: 1.0
Sprint: F-011
Status: Stable

Purpose:
Extract relationships between documents.
"""

from __future__ import annotations

import re

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph


class RelationExtractor:
    """
    Extracts document references from document content.

    Example:
        ADR-0001
        ADR-0002
        KCS-001
    """

    ADR_PATTERN = re.compile(r"\bADR-\d{4}\b")
    KCS_PATTERN = re.compile(r"\bKCS-\d+(?:\.\d+)?\b")

    def extract(self, graph: KnowledgeGraph) -> None:

        nodes = list(graph.nodes.values())

        lookup = {}

        for node in nodes:

            lookup[node.name] = node

            source = getattr(node, "source", "")

            if source:
                lookup[source] = node

        for node in nodes:

            document = getattr(node, "document", None)

            if document is None:
                continue

            content = getattr(document, "content", "")

            references = set()

            references.update(
                self.ADR_PATTERN.findall(content)
            )

            references.update(
                self.KCS_PATTERN.findall(content)
            )

            for reference in sorted(references):

                target = lookup.get(reference)

                if target is None:
                    continue

                graph.add_edge(
                    KnowledgeEdge(
                        source=node.id,
                        target=target.id,
                    )
                )