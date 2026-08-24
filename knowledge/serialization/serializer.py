"""KnowledgeGraph serializer."""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph


class GraphSerializer:
    """Serialize KnowledgeGraph into a versioned wire-format dictionary."""

    SCHEMA_VERSION = "1.0.0"

    def serialize(self, graph: KnowledgeGraph) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
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
