"""
Knowledge Operating System (KOS)

File: knowledge/serialization/deserializer.py
Version: 2.1
Sprint: GRAPH-012

Deserialize a dictionary into KnowledgeGraph.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType

E = TypeVar("E", bound=Enum)


class DeserializationError(ValueError):
    """Raised when graph payload is invalid."""


def _parse_enum(enum_cls: type[E], value: Any, default: E) -> E:
    if value is None:
        return default
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, Enum):
        value = value.name
    text = str(value).strip()
    if not text:
        return default
    if text in enum_cls.__members__:
        return enum_cls[text]
    upper = text.upper()
    if upper in enum_cls.__members__:
        return enum_cls[upper]
    try:
        return enum_cls(text)
    except ValueError:
        try:
            return enum_cls(text.lower())
        except ValueError:
            return default


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class GraphDeserializer:
    """Deserialize a Python dictionary into a KnowledgeGraph."""

    def __init__(self, *, strict: bool = False) -> None:
        """
        strict=False — tolerant mode (legacy tests, partial payloads).
        strict=True  — require id/source/target and valid root structure.
        """
        self.strict = strict

    def deserialize(self, data: dict[str, Any]) -> KnowledgeGraph:
        if not isinstance(data, dict):
            raise DeserializationError("Serialized graph must be a dictionary.")

        if self.strict:
            self._validate_root(data)

        nodes_raw = data.get("nodes", []) or []
        edges_raw = data.get("edges", []) or []

        if not isinstance(nodes_raw, list):
            raise DeserializationError("'nodes' must be a list.")
        if not isinstance(edges_raw, list):
            raise DeserializationError("'edges' must be a list.")

        graph = KnowledgeGraph()

        for index, node_data in enumerate(nodes_raw):
            if not isinstance(node_data, dict):
                raise DeserializationError(
                    f"Node at index {index} must be a dictionary."
                )
            graph.add_node(self._node_from_dict(node_data, index=index))

        for index, edge_data in enumerate(edges_raw):
            if not isinstance(edge_data, dict):
                raise DeserializationError(
                    f"Edge at index {index} must be a dictionary."
                )
            graph.add_edge(self._edge_from_dict(edge_data, index=index))

        return graph

    def _validate_root(self, data: dict[str, Any]) -> None:
        missing = {"nodes", "edges"} - set(data.keys())
        if missing:
            raise DeserializationError(f"Missing keys: {sorted(missing)}")

    def _node_from_dict(
        self,
        data: dict[str, Any],
        *,
        index: int,
    ) -> KnowledgeNode:
        node_id = data.get("id")
        if node_id is None or str(node_id).strip() == "":
            raise DeserializationError(
                f"Node at index {index} is missing required field 'id'."
            )

        kwargs: dict[str, Any] = {
            "id": str(node_id),
            "type": _parse_enum(NodeType, data.get("type"), NodeType.DOCUMENT),
            "name": data.get("name", "") or "",
            "source": data.get("source", "") or "",
            "description": data.get("description", "") or "",
            "confidence": float(
                data.get("confidence", 1.0)
                if data.get("confidence") is not None
                else 1.0
            ),
            "status": data.get("status", "ACTIVE") or "ACTIVE",
            "metadata": dict(data.get("metadata") or {}),
            "tags": set(data.get("tags") or []),
        }

        if self.strict and not str(kwargs["name"]).strip():
            raise DeserializationError(
                f"Node '{kwargs['id']}' is missing required field 'name' (strict mode)."
            )

        created = _parse_dt(data.get("created_at"))
        updated = _parse_dt(data.get("updated_at"))
        if created is not None:
            kwargs["metadata"]["created_at"] = created.isoformat()
        if updated is not None:
            kwargs["metadata"]["updated_at"] = updated.isoformat()

        return KnowledgeNode(**kwargs)

    def _edge_from_dict(
        self,
        data: dict[str, Any],
        *,
        index: int,
    ) -> KnowledgeEdge:
        source = data.get("source")
        target = data.get("target")

        if source is None or str(source).strip() == "":
            raise DeserializationError(
                f"Edge at index {index} is missing required field 'source'."
            )
        if target is None or str(target).strip() == "":
            raise DeserializationError(
                f"Edge at index {index} is missing required field 'target'."
            )

        kwargs: dict[str, Any] = {
            "source": str(source),
            "target": str(target),
            "type": _parse_enum(EdgeType, data.get("type"), EdgeType.REFERENCES),
            "description": data.get("description", "") or "",
            "confidence": float(
                data.get("confidence", 1.0)
                if data.get("confidence") is not None
                else 1.0
            ),
        }

        edge_id = data.get("id")
        if edge_id is not None and str(edge_id).strip() != "":
            kwargs["id"] = str(edge_id)

        metadata = dict(data.get("metadata") or {})
        weight = data.get("weight")
        if weight is not None:
            metadata["weight"] = float(weight)
        status = data.get("status")
        if status is not None:
            metadata["status"] = status
        created = _parse_dt(data.get("created_at"))
        updated = _parse_dt(data.get("updated_at"))
        if created is not None:
            metadata["created_at"] = created.isoformat()
        if updated is not None:
            metadata["updated_at"] = updated.isoformat()
        if metadata:
            kwargs["metadata"] = metadata

        return KnowledgeEdge(**kwargs)
