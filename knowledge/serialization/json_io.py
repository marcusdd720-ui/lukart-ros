"""JSON persistence for KnowledgeGraph."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.graph import KnowledgeGraph
from knowledge.serialization.deserializer import GraphDeserializer
from knowledge.serialization.schema import GraphSchemaValidator
from knowledge.serialization.serializer import GraphSerializer


class GraphJsonIO:
    """Read and write KnowledgeGraph objects as validated JSON."""

    def save(self, graph: KnowledgeGraph, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = GraphSerializer().serialize(graph)
        with destination.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)

    def load(self, path: str | Path) -> KnowledgeGraph:
        with Path(path).open(encoding="utf-8") as fp:
            data = json.load(fp)
        GraphSchemaValidator().validate(data)
        return GraphDeserializer(strict=True).deserialize(data)
