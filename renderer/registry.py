"""Explicit registry for deterministic reasoning renderers."""

from __future__ import annotations

from renderer.contract import ReasoningRenderer, RendererKind


class RendererRegistry:
    """Map one renderer kind to exactly one active renderer implementation."""

    def __init__(self) -> None:
        self._renderers: dict[RendererKind, ReasoningRenderer] = {}

    def register(self, renderer: ReasoningRenderer) -> None:
        if not renderer.version.strip():
            raise ValueError("renderer version is required")
        if renderer.kind in self._renderers:
            raise ValueError(f"renderer already registered for kind: {renderer.kind.value}")
        self._renderers[renderer.kind] = renderer

    def require(self, kind: RendererKind) -> ReasoningRenderer:
        renderer = self._renderers.get(kind)
        if renderer is None:
            raise KeyError(f"renderer not registered for kind: {kind.value}")
        return renderer

    def kinds(self) -> tuple[RendererKind, ...]:
        return tuple(sorted(self._renderers, key=lambda item: item.value))
