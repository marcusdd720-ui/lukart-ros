"""
Knowledge Operating System (KOS)

File: knowledge/document.py
Version: 2.1
Sprint: F-009
Status: Stable

Purpose:
Represents a repository document and converts it into
a KnowledgeNode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from knowledge.metadata import Metadata
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


@dataclass(slots=True)
class Document:
    """Repository document."""

    path: Path
    name: str
    extension: str
    size: int
    modified: datetime

    metadata: Metadata = field(default_factory=Metadata)

    content: str = ""

    logical_id: str = ""

    content_hash: str = ""

    version: str = "1.0"

    @classmethod
    def from_file(cls, path: Path) -> Document:

        stat = path.stat()

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="ignore")

        document = cls(
            path=path,
            name=path.name,
            extension=path.suffix,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
            content=content,
        )

        document.calculate_hash()

        return document

    def calculate_hash(self) -> None:
        """Calculate SHA-256 of document content."""

        self.content_hash = sha256(self.content.encode("utf-8")).hexdigest()

    def to_node(self) -> KnowledgeNode:
        """Convert document into KnowledgeNode."""

        node_name = self.metadata.title if self.metadata.title else self.name

        self.logical_id = (
            self.metadata.document_id if self.metadata.document_id else self.name
        )

        return KnowledgeNode(
            name=node_name,
            type=NodeType.DOCUMENT,
            source=str(self.path),
        )

    def __str__(self) -> str:

        return f"{self.logical_id} | {self.name} | {self.content_hash[:8]}"
