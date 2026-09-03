"""Typed contracts for deterministic ReasoningRunResult renderers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from reasoning.models import ReasoningRunResult


class RendererKind(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"
    EVIDENCE_LIST = "evidence_list"


@dataclass(frozen=True, slots=True)
class RenderedResult:
    """Immutable presentation artifact bound to one reasoning-result digest."""

    kind: RendererKind
    media_type: str
    content: str
    source_digest: str
    renderer_version: str

    def __post_init__(self) -> None:
        media_type = self.media_type.strip()
        source_digest = self.source_digest.strip()
        renderer_version = self.renderer_version.strip()
        if not media_type or not self.content or not source_digest or not renderer_version:
            raise ValueError("rendered result fields cannot be blank")
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "source_digest", source_digest)
        object.__setattr__(self, "renderer_version", renderer_version)


class ReasoningRenderer(Protocol):
    """Renderer boundary: presentation may read reasoning state but never mutate it."""

    kind: RendererKind
    version: str

    def render(self, result: ReasoningRunResult) -> RenderedResult:
        """Render a deterministic presentation artifact."""
        ...
