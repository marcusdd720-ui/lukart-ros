"""
Knowledge Operating System (KOS)

Sprint GRAPH-011

KnowledgeGraph serializer.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph


class GraphSerializer:
    """
    Serialize KnowledgeGraph into a Python dictionary.
    """

    def serialize(
        self,
        graph: KnowledgeGraph,
    ) -> dict:

        return {
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.name,
                    "name": node.name,
                    "source": node.source,
                    "description": node.description,
                }
                for node in graph.nodes.values()
            ],
            "edges": [
                {
                    "id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type.name,
                    "description": edge.description,
                }
                for edge in graph.edges
            ],
        }
