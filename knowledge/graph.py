from knowledge.node import KnowledgeNode
from knowledge.edge import KnowledgeEdge


class KnowledgeGraph:
    """Pierwszy graf wiedzy KOS."""

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node: KnowledgeNode):
        self.nodes[node.id] = node

    def add_edge(self, edge: KnowledgeEdge):
        self.edges.append(edge)

    def find_by_name(self, name: str):
        for node in self.nodes.values():
            if node.name == name:
                return node
        return None

    def node_count(self):
        return len(self.nodes)

    def edge_count(self):
        return len(self.edges)

    def __str__(self):
        return (
            f"KnowledgeGraph("
            f"nodes={self.node_count()}, "
            f"edges={self.edge_count()})"
        )