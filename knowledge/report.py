"""
Knowledge Operating System (KOS)

File: knowledge/report.py
Version: 1.0
Sprint: F-011
Status: Stable

Purpose:
Generates a simple graph report.
"""

from knowledge.graph import KnowledgeGraph


class GraphReport:
    """Simple graph report."""

    def generate(self, graph: KnowledgeGraph) -> str:

        lines = []

        lines.append("=" * 60)
        lines.append("Knowledge Graph Report")
        lines.append("=" * 60)
        lines.append(f"Nodes : {graph.node_count()}")
        lines.append(f"Edges : {graph.edge_count()}")
        lines.append("")

        lines.append("Nodes")
        lines.append("-" * 60)

        for node in graph.nodes.values():
            lines.append(f"{node.name} [{node.type}]")

        lines.append("")
        lines.append("Edges")
        lines.append("-" * 60)

        for edge in graph.edges:
            lines.append(f"{edge.source} -> {edge.target} ({edge.type})")

        lines.append("")
        lines.append("End of report")

        return "\n".join(lines)
