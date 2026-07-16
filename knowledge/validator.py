"""
Knowledge Operating System (KOS)

File: knowledge/validator.py
Version: 1.0
Sprint: F-011
Status: Stable

Purpose:
Validates the Knowledge Graph.
"""

from knowledge.graph import KnowledgeGraph


class GraphValidator:
    """Basic graph validator."""

    def validate(self, graph: KnowledgeGraph):

        errors = []

        if graph.node_count() == 0:
            errors.append("Graph contains no nodes.")

        node_ids = set()

        for node in graph.nodes.values():

            if node.id in node_ids:
                errors.append(
                    f"Duplicate node id: {node.id}"
                )

            node_ids.add(node.id)

            if not node.name:
                errors.append(
                    f"Node {node.id} has no name."
                )

        for edge in graph.edges:

            if edge.source not in graph.nodes:
                errors.append(
                    f"Missing source node: {edge.source}"
                )

            if edge.target not in graph.nodes:
                errors.append(
                    f"Missing target node: {edge.target}"
                )

        return errors

    def print_report(self, graph: KnowledgeGraph):

        errors = self.validate(graph)

        print("=" * 60)
        print("Validation Report")
        print("=" * 60)

        if not errors:
            print("Status : PASSED")
            print("Errors : 0")
            return

        print("Status : FAILED")
        print()

        for error in errors:
            print(f"- {error}")