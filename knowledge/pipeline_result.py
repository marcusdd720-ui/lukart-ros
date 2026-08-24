"""Structured result model for the Knowledge pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from knowledge.graph import KnowledgeGraph


class PipelineStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(slots=True)
class PipelineResult:
    """Auditable outcome of one pipeline execution."""

    status: PipelineStatus
    graph: KnowledgeGraph | None = None
    confidence_score: float | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stage_results: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is PipelineStatus.SUCCESS

    @property
    def has_output(self) -> bool:
        return self.graph is not None

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
