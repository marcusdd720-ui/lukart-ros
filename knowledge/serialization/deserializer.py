"""
Knowledge Operating System (KOS)

Sprint GRAPH-012

KnowledgeGraph deserializer.
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


class GraphDeserializer:
    """
    Deserialize a Python dictionary into a KnowledgeGraph.
    """

    def deserialize(
        self,
        data: dict,
    ) -> KnowledgeGraph:

        graph = KnowledgeGraph()

        for node_data in data.get("nodes", []):
            graph.add_node(
                KnowledgeNode(
                    id=node_data["id"],
                    type=node_data.get("type"),
                    name=node_data.get("name", ""),
                    source=node_data.get("source", ""),
                    description=node_data.get("description", ""),
                )
            )

        for edge_data in data.get("edges", []):
            graph.add_edge(
                KnowledgeEdge(
                    id=edge_data["id"],
                    source=edge_data["source"],
                    target=edge_data["target"],
                    type=edge_data.get("type"),
                    description=edge_data.get("description", ""),
                )
            )

        return graph
