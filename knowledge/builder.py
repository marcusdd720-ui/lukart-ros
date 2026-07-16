"""
Knowledge Operating System (KOS)

File: knowledge/builder.py
Version: 1.0
Status: Stable
Sprint: F-008

Purpose:
Builds the first Knowledge Graph from Markdown documents.
"""

from knowledge.loader import DocumentLoader
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


class GraphBuilder:
    """Builds a KnowledgeGraph from repository documents."""

    def __init__(self, root: str = "."):
        self.loader = DocumentLoader(root)

    def build(self) -> KnowledgeGraph:
        graph = KnowledgeGraph()

        documents = self.loader.load_documents()

        for document in documents:
            node = KnowledgeNode(
                name=document.name,
                type=NodeType.DOCUMENT,
                source=str(document.path),
            )

            graph.add_node(node)

        return graph


def main():
    print("=" * 50)
    print("Knowledge Operating System")
    print("Graph Builder")
    print("=" * 50)

    builder = GraphBuilder()
    graph = builder.build()

    print()
    print(graph)

    print()
    print("Nodes")

    for node in graph.nodes.values():
        print(f" - {node.name}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()