"""
Knowledge Operating System (KOS)

Sprint GRAPH-013

JSON persistence for KnowledgeGraph.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.graph import KnowledgeGraph
from knowledge.serialization.deserializer import GraphDeserializer
from knowledge.serialization.serializer import GraphSerializer


class GraphJsonIO:
    """
    Read and write KnowledgeGraph objects as JSON.
    """

    def save(
        self,
        graph: KnowledgeGraph,
        path: str | Path,
    ) -> None:

        data = GraphSerializer().serialize(graph)

        with open(path, "w", encoding="utf-8") as fp:
            json.dump(
                data,
                fp,
                indent=2,
                ensure_ascii=False,
            )

    def load(
        self,
        path: str | Path,
    ) -> KnowledgeGraph:

        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)

        return GraphDeserializer().deserialize(data)
