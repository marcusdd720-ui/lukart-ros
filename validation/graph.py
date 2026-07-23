"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 4.0
Sprint: GRAPH-018

High-performance directed Knowledge Graph.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Set

from core.models.ids import EntityId

from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


# ============================================================
# Exceptions
# ============================================================


class GraphError(Exception):
    """Base class for graph exceptions."""


class NodeAlreadyExists(GraphError):
    """Raised when a node already exists."""


class NodeNotFound(GraphError):
    """Raised when a node cannot be found."""


class EdgeAlreadyExists(GraphError):
    """Raised when an edge already exists."""


class EdgeNotFound(GraphError):
    """Raised when an edge cannot be found."""


class GraphValidationError(GraphError):
    """Raised when graph validation fails."""


# ============================================================
# Type aliases
# ============================================================


NodeDict = Dict[EntityId, KnowledgeNode]
EdgeList = List[KnowledgeEdge]
NeighborSet = Set[EntityId]


# ============================================================
# Knowledge Graph
# ============================================================


@dataclass(slots=True)
class KnowledgeGraph:
    """
    Directed graph optimized for Knowledge Operating System.
    """

    nodes: NodeDict = field(default_factory=dict)

    edges: EdgeList = field(default_factory=list)

    adjacency: Dict[EntityId, NeighborSet] = field(
        default_factory=dict
    )

    reverse_adjacency: Dict[EntityId, NeighborSet] = field(
        default_factory=dict
    )

    # --------------------------------------------------------
    # Construction
    # --------------------------------------------------------

    def __post_init__(self) -> None:
        """Synchronize indexes after dataclass construction."""
        self._rebuild_indexes()

    def clear(self) -> None:
        """Remove every node and edge."""
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        self.reverse_adjacency.clear()

    def is_empty(self) -> bool:
        """Return True if graph has no nodes."""
        return not self.nodes

    def copy(self) -> "KnowledgeGraph":
        """Deep copy."""
        return deepcopy(self)

    def __len__(self) -> int:
        return len(self.nodes)

    def __bool__(self) -> bool:
        return bool(self.nodes)

    def __iter__(self) -> Iterator[KnowledgeNode]:
        return iter(self.nodes.values())

    def __contains__(self, node_id: EntityId) -> bool:
        return node_id in self.nodes

    def __repr__(self) -> str:
        return (
            "KnowledgeGraph("
            f"nodes={len(self.nodes)}, "
            f"edges={len(self.edges)})"
        )

    # --------------------------------------------------------
    # Internal index management
    # --------------------------------------------------------

    def _rebuild_indexes(self) -> None:
        """Rebuild adjacency indexes from edge list."""
        self.adjacency.clear()
        self.reverse_adjacency.clear()

        for node_id in self.nodes:
            self.adjacency.setdefault(node_id, set())
            self.reverse_adjacency.setdefault(node_id, set())

        for edge in self.edges:
            self.adjacency.setdefault(edge.source, set()).add(
                edge.target
            )
            self.reverse_adjacency.setdefault(
                edge.target,
                set(),
            ).add(edge.source)

    # --------------------------------------------------------
    # Node API
    # --------------------------------------------------------

    def add_node(
        self,
        node: KnowledgeNode,
    ) -> None:
        """Add a node to the graph."""
        if node.id in self.nodes:
            raise NodeAlreadyExists(
                f"Node '{node.id}' already exists."
            )

        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, set())
        self.reverse_adjacency.setdefault(node.id, set())

    def add_nodes(
        self,
        nodes: Iterable[KnowledgeNode],
    ) -> None:
        """Add multiple nodes."""
        for node in nodes:
            self.add_node(node)

    def get_node(
        self,
        node_id: EntityId,
    ) -> Optional[KnowledgeNode]:
        """Return node or None."""
        return self.nodes.get(node_id)

    def contains_node(
        self,
        node_id: EntityId,
    ) -> bool:
        """Check whether node exists."""
        return node_id in self.nodes

    def has_node(
        self,
        node_id: EntityId,
    ) -> bool:
        """Alias for contains_node()."""
        return self.contains_node(node_id)

    def remove_node(
        self,
        node_id: EntityId,
    ) -> None:
        """Remove node together with all connected edges."""
        if node_id not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{node_id}'."
            )

        del self.nodes[node_id]

        self.edges = [
            edge
            for edge in self.edges
            if edge.source != node_id
            and edge.target != node_id
        ]

        self._rebuild_indexes()

    def node_count(self) -> int:
        """Return number of nodes."""
        return len(self.nodes)

    def nodes_iter(self) -> Iterator[KnowledgeNode]:
        """Iterate over nodes."""
        return iter(self.nodes.values())

    # --------------------------------------------------------
    # Edge API
    # --------------------------------------------------------

    def add_edge(
        self,
        edge: KnowledgeEdge,
    ) -> None:
        """Add edge to graph."""
        if edge.source not in self.nodes:
            raise NodeNotFound(
                f"Unknown source node '{edge.source}'."
            )

        if edge.target not in self.nodes:
            raise NodeNotFound(
                f"Unknown target node '{edge.target}'."
            )

        if self.contains_edge(
            edge.source,
            edge.target,
        ):
            raise EdgeAlreadyExists(
                f"Edge '{edge.source}' -> "
                f"'{edge.target}' already exists."
            )

        self.edges.append(edge)

        self.adjacency.setdefault(
            edge.source,
            set(),
        ).add(edge.target)

        self.reverse_adjacency.setdefault(
            edge.target,
            set(),
        ).add(edge.source)

    def add_edges(
        self,
        edges: Iterable[KnowledgeEdge],
    ) -> None:
        """Add multiple edges."""
        for edge in edges:
            self.add_edge(edge)

    def get_edge(
        self,
        source: EntityId,
        target: EntityId,
    ) -> Optional[KnowledgeEdge]:
        """Return edge or None."""
        for edge in self.edges:
            if (
                edge.source == source
                and edge.target == target
            ):
                return edge

        return None

    def contains_edge(
        self,
        source: EntityId,
        target: EntityId,
    ) -> bool:
        """Check whether edge exists."""
        return (
            self.get_edge(
                source,
                target,
            )
            is not None
        )

    def remove_edge(
        self,
        source: EntityId,
        target: EntityId,
    ) -> bool:
        """Remove edge from graph."""
        edge = self.get_edge(
            source,
            target,
        )

        if edge is None:
            return False

        self.edges.remove(edge)

        self.adjacency.get(
            source,
            set(),
        ).discard(target)

        self.reverse_adjacency.get(
            target,
            set(),
        ).discard(source)

        return True

    def edge_count(self) -> int:
        """Return number of edges."""
        return len(self.edges)

    # --------------------------------------------------------
    # Neighbour API
    # --------------------------------------------------------

    def successors(
        self,
        node_id: EntityId,
    ) -> List[KnowledgeNode]:
        """Return successor nodes."""
        result: List[KnowledgeNode] = []

        for successor_id in self.adjacency.get(
            node_id,
            set(),
        ):
            node = self.nodes.get(successor_id)

            if node is not None:
                result.append(node)

        return result

    def predecessors(
        self,
        node_id: EntityId,
    ) -> List[KnowledgeNode]:
        """Return predecessor nodes."""
        result: List[KnowledgeNode] = []

        for predecessor_id in self.reverse_adjacency.get(
            node_id,
            set(),
        ):
            node = self.nodes.get(predecessor_id)

            if node is not None:
                result.append(node)

        return result

    def neighbors(
        self,
        node_id: EntityId,
    ) -> List[KnowledgeNode]:
        """Alias for successors()."""
        return self.successors(node_id)

    def out_degree(
        self,
        node_id: EntityId,
    ) -> int:
        """Return outgoing degree."""
        return len(
            self.adjacency.get(
                node_id,
                set(),
            )
        )

    def in_degree(
        self,
        node_id: EntityId,
    ) -> int:
        """Return incoming degree."""
        return len(
            self.reverse_adjacency.get(
                node_id,
                set(),
            )
        )

    def degree(
        self,
        node_id: EntityId,
    ) -> int:
        """Return total degree."""
        return (
            self.in_degree(node_id)
            + self.out_degree(node_id)
        )

    # --------------------------------------------------------
    # Graph Traversal
    # --------------------------------------------------------

    def bfs(
        self,
        start: EntityId,
    ) -> List[KnowledgeNode]:
        """Breadth-first traversal."""
        if start not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{start}'."
            )

        visited: Set[EntityId] = set()
        queue: deque[EntityId] = deque([start])
        result: List[KnowledgeNode] = []

        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            node = self.nodes.get(current)
            if node is not None:
                result.append(node)

            for neighbour in self.adjacency.get(
                current,
                set(),
            ):
                if neighbour not in visited:
                    queue.append(neighbour)

        return result

    def dfs(
        self,
        start: EntityId,
    ) -> List[KnowledgeNode]:
        """Depth-first traversal."""
        if start not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{start}'."
            )

        visited: Set[EntityId] = set()
        stack: List[EntityId] = [start]
        result: List[KnowledgeNode] = []

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)

            node = self.nodes.get(current)
            if node is not None:
                result.append(node)

            neighbours = sorted(
                self.adjacency.get(
                    current,
                    set(),
                ),
                reverse=True,
            )

            stack.extend(neighbours)

        return result

    def has_path(
        self,
        source: EntityId,
        target: EntityId,
    ) -> bool:
        """Return True when path exists."""
        if source == target:
            return source in self.nodes

        visited: Set[EntityId] = set()
        queue: deque[EntityId] = deque([source])

        while queue:
            current = queue.popleft()

            if current == target:
                return True

            if current in visited:
                continue

            visited.add(current)

            queue.extend(
                self.adjacency.get(
                    current,
                    set(),
                )
            )

        return False

    def shortest_path(
        self,
        source: EntityId,
        target: EntityId,
    ) -> List[KnowledgeNode]:
        """Return shortest path using BFS."""
        if source not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{source}'."
            )

        if target not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{target}'."
            )

        if source == target:
            return [self.nodes[source]]

        queue: deque[EntityId] = deque([source])
        visited: Set[EntityId] = {source}
        previous: Dict[EntityId, EntityId] = {}

        while queue:
            current = queue.popleft()

            for neighbour in self.adjacency.get(
                current,
                set(),
            ):
                if neighbour in visited:
                    continue

                visited.add(neighbour)
                previous[neighbour] = current

                if neighbour == target:
                    queue.clear()
                    break

                queue.append(neighbour)

        if target not in previous:
            return []

        path: List[EntityId] = [target]

        while path[-1] != source:
            path.append(previous[path[-1]])

        path.reverse()

        return [
            self.nodes[node_id]
            for node_id in path
        ]

    # --------------------------------------------------------
    # Iterators
    # --------------------------------------------------------

    def iter_nodes(
        self,
    ) -> Iterator[KnowledgeNode]:
        """Iterate over all nodes."""
        yield from self.nodes.values()

    def iter_edges(
        self,
    ) -> Iterator[KnowledgeEdge]:
        """Iterate over all edges."""
        yield from self.edges

    def iter_successors(
        self,
        node_id: EntityId,
    ) -> Iterator[KnowledgeNode]:
        """Iterate over successor nodes."""
        for neighbour_id in self.adjacency.get(
            node_id,
            set(),
        ):
            node = self.nodes.get(neighbour_id)

            if node is not None:
                yield node

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def validate(self) -> None:
        """Validate graph consistency."""
        errors = self._validate_graph()

        if errors:
            raise GraphValidationError(
                "\n".join(errors)
            )

    def _validate_graph(self) -> List[str]:
        """Internal graph validation."""
        errors: List[str] = []

        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(
                    f"Missing source node: {edge.source}"
                )

            if edge.target not in self.nodes:
                errors.append(
                    f"Missing target node: {edge.target}"
                )

        for source, targets in self.adjacency.items():
            if source not in self.nodes:
                errors.append(
                    f"Adjacency references "
                    f"unknown node: {source}"
                )

            for target in targets:
                if target not in self.nodes:
                    errors.append(
                        f"Adjacency contains "
                        f"unknown target: {target}"
                    )

                if not self.contains_edge(
                    source,
                    target,
                ):
                    errors.append(
                        f"Missing edge "
                        f"{source} -> {target}"
                    )

        for target, sources in (
            self.reverse_adjacency.items()
        ):
            if target not in self.nodes:
                errors.append(
                    f"Reverse adjacency "
                    f"references unknown node: "
                    f"{target}"
                )

            for source in sources:
                if source not in self.nodes:
                    errors.append(
                        f"Reverse adjacency "
                        f"contains unknown source: "
                        f"{source}"
                    )

                if not self.contains_edge(
                    source,
                    target,
                ):
                    errors.append(
                        f"Missing reverse edge "
                        f"{source} -> {target}"
                    )

        return errors

    # --------------------------------------------------------
    # Serialization
    # --------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph."""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "KnowledgeGraph":
        """Create graph from dictionary."""
        graph = cls()

        graph.add_nodes(
            data.get("nodes", [])
        )

        graph.add_edges(
            data.get("edges", [])
        )

        return graph

    # --------------------------------------------------------
    # Utilities
    # --------------------------------------------------------

    def subgraph(
        self,
        node_ids: Iterable[EntityId],
    ) -> "KnowledgeGraph":
        """Create subgraph."""
        graph = KnowledgeGraph()

        selected = set(node_ids)

        for node_id in selected:
            node = self.nodes.get(node_id)

            if node is not None:
                graph.add_node(
                    deepcopy(node)
                )

        for edge in self.edges:
            if (
                edge.source in selected
                and edge.target in selected
            ):
                graph.add_edge(
                    deepcopy(edge)
                )

        return graph

    def merge(
        self,
        other: "KnowledgeGraph",
    ) -> None:
        """Merge another graph."""
        for node in other.nodes.values():
            if not self.contains_node(node.id):
                self.add_node(
                    deepcopy(node)
                )

        for edge in other.edges:
            if not self.contains_edge(
                edge.source,
                edge.target,
            ):
                self.add_edge(
                    deepcopy(edge)
                )

    def to_adjacency_dict(
        self,
    ) -> Dict[
        EntityId,
        List[EntityId],
    ]:
        """Return adjacency dictionary."""
        return {
            node: sorted(targets)
            for node, targets
            in self.adjacency.items()
        }

    def leaves(self) -> List[KnowledgeNode]:
        """Return leaf nodes."""
        return [
            node
            for node in self.nodes.values()
            if self.out_degree(node.id) == 0
        ]

    def roots(self) -> List[KnowledgeNode]:
        """Return root nodes."""
        return [
            node
            for node in self.nodes.values()
            if self.in_degree(node.id) == 0
        ]

    def isolated_nodes(
        self,
    ) -> List[KnowledgeNode]:
        """Return isolated nodes."""
        return [
            node
            for node in self.nodes.values()
            if self.degree(node.id) == 0
        ]

    def copy_nodes_from(
        self,
        other: "KnowledgeGraph",
    ) -> None:
        """Copy only nodes from another graph."""
        for node in other.nodes.values():
            if not self.contains_node(node.id):
                self.add_node(
                    deepcopy(node)
                )

    def copy_edges_from(
        self,
        other: "KnowledgeGraph",
    ) -> None:
        """Copy only edges from another graph."""
        for edge in other.edges:
            if not self.contains_edge(
                edge.source,
                edge.target,
            ):
                self.add_edge(
                    deepcopy(edge)
                )

    def update_node(
        self,
        node: KnowledgeNode,
    ) -> None:
        """Replace existing node."""
        if node.id not in self.nodes:
            raise NodeNotFound(
                f"Unknown node '{node.id}'."
            )

        self.nodes[node.id] = node

    def update_edge(
        self,
        edge: KnowledgeEdge,
    ) -> None:
        """Replace existing edge."""
        current = self.get_edge(
            edge.source,
            edge.target,
        )

        if current is None:
            raise EdgeNotFound(
                f"Unknown edge "
                f"{edge.source}->{edge.target}"
            )

        index = self.edges.index(current)
        self.edges[index] = edge

    def clear_edges(self) -> None:
        """Remove every edge."""
        self.edges.clear()

        for neighbours in self.adjacency.values():
            neighbours.clear()

        for neighbours in (
            self.reverse_adjacency.values()
        ):
            neighbours.clear()

    def clear_nodes(self) -> None:
        """Remove every node."""
        self.clear()

    def graph_statistics(
        self,
    ) -> Dict[str, int]:
        """Return graph statistics."""
        return {
            "nodes": self.node_count(),
            "edges": self.edge_count(),
            "roots": len(self.roots()),
            "leaves": len(self.leaves()),
            "isolated": len(
                self.isolated_nodes()
            ),
        }

    # --------------------------------------------------------
    # Cycle Detection
    # --------------------------------------------------------

    def has_cycle(self) -> bool:
        """Return True if graph contains a cycle."""
        visited: Set[EntityId] = set()
        active: Set[EntityId] = set()

        for node_id in self.nodes:
            if node_id not in visited:
                if self._has_cycle(
                    node_id,
                    visited,
                    active,
                ):
                    return True

        return False

    def _has_cycle(
        self,
        node_id: EntityId,
        visited: Set[EntityId],
        active: Set[EntityId],
    ) -> bool:
        """Depth-first cycle detection."""
        visited.add(node_id)
        active.add(node_id)

        for successor in self.adjacency.get(
            node_id,
            set(),
        ):
            if successor not in visited:
                if self._has_cycle(
                    successor,
                    visited,
                    active,
                ):
                    return True

            elif successor in active:
                return True

        active.remove(node_id)
        return False

    # --------------------------------------------------------
    # Topological Sort
    # --------------------------------------------------------

    def topological_sort(
        self,
    ) -> List[KnowledgeNode]:
        """Return nodes in topological order."""
        if self.has_cycle():
            raise GraphValidationError(
                "Graph contains a cycle."
            )

        indegree: Dict[
            EntityId,
            int,
        ] = {
            node_id: self.in_degree(node_id)
            for node_id in self.nodes
        }

        queue: deque[
            EntityId
        ] = deque(
            node_id
            for node_id, degree
            in indegree.items()
            if degree == 0
        )

        result: List[
            KnowledgeNode
        ] = []

        while queue:
            node_id = queue.popleft()

            result.append(
                self.nodes[node_id]
            )

            for successor in self.adjacency.get(
                node_id,
                set(),
            ):
                indegree[successor] -= 1

                if indegree[successor] == 0:
                    queue.append(successor)

        return result

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------

    def adjacency_matrix(
        self,
    ) -> Dict[EntityId, Dict[EntityId, bool]]:
        """Return adjacency matrix."""
        matrix: Dict[
            EntityId,
            Dict[EntityId, bool],
        ] = {}

        for source in self.nodes:
            row: Dict[EntityId, bool] = {}

            for target in self.nodes:
                row[target] = self.contains_edge(
                    source,
                    target,
                )

            matrix[source] = row

        return matrix

    def edge_pairs(
        self,
    ) -> List[tuple[EntityId, EntityId]]:
        """Return every edge as source-target tuple."""
        return [
            (
                edge.source,
                edge.target,
            )
            for edge in self.edges
        ]

    def node_ids(self) -> List[EntityId]:
        """Return node identifiers."""
        return list(self.nodes.keys())

    def edge_ids(self) -> List[str]:
        """Return edge identifiers."""
        return [
            edge.id
            for edge in self.edges
        ]

    def rebuild(self) -> None:
        """Rebuild graph indexes."""
        self._rebuild_indexes()

    def sort_edges(self) -> None:
        """Sort edges deterministically."""
        self.edges.sort(
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.id,
            )
        )

    def sort_nodes(self) -> None:
        """Sort nodes deterministically."""
        self.nodes = dict(
            sorted(
                self.nodes.items(),
                key=lambda item: item[0],
            )
        )

    def normalize(self) -> None:
        """Normalize graph."""
        self.sort_nodes()
        self.sort_edges()
        self.rebuild()

    def __eq__(
        self,
        other: object,
    ) -> bool:
        """Compare two graphs."""
        if not isinstance(
            other,
            KnowledgeGraph,
        ):
            return False

        return (
            self.nodes == other.nodes
            and self.edges == other.edges
        )
