"""KDOC adapter over existing deterministic reasoning renderers."""

from __future__ import annotations

from knowledge.models.document_binding import BoundRenderedDocument, DocumentBinding
from renderer.contract import RenderedResult


def bind_rendered_result(
    rendered: RenderedResult,
    binding: DocumentBinding,
) -> BoundRenderedDocument:
    """Bind an existing deterministic render without adding analysis or authority."""
    if rendered.source_digest != binding.source_digest:
        raise ValueError("renderer source digest does not match KDOC binding")
    if rendered.renderer_version != binding.renderer_version:
        raise ValueError("renderer version does not match KDOC binding")
    return BoundRenderedDocument(
        binding=binding,
        media_type=rendered.media_type,
        content=rendered.content,
    )
