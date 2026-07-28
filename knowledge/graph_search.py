"""
Knowledge Operating System (KOS)

File: knowledge/graph_search.py
Version: 1.0
Sprint: F-012
Status: Stable
"""

from knowledge.graph import KnowledgeGraph


class GraphSearch:
    """Simple graph search API."""

    def __init__(self, graph: KnowledgeGraph):

        self.graph = graph

    def find_by_name(self, name: str):

        for node in self.graph.nodes.values():
            if node.name == name:
                return node

        return None

    def neighbours(self, node_id: str):

        result = []

        for edge in self.graph.edges:
            if edge.source == node_id:
                target = self.graph.get_node(edge.target)

                if target:
                    result.append(target)

        return result

    def incoming(self, node_id: str):

        result = []

        for edge in self.graph.edges:
            if edge.target == node_id:
                source = self.graph.get_node(edge.source)

                if source:
                    result.append(source)

        return result
