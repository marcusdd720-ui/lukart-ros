import pytest

from knowledge.models.document_binding import DocumentBinding
from renderer.contract import RenderedResult, RendererKind
from renderer.document import bind_rendered_result


def _binding(*, digest: str = "digest", version: str = "renderer-v1") -> DocumentBinding:
    return DocumentBinding(
        document_id="DOC-1",
        renderer_id="reasoning-markdown",
        renderer_version=version,
        template_id="dossier",
        template_version="v1",
        input_refs=(),
        source_digest=digest,
        generated_at="2026-09-05T04:20:00Z",
        communication_target="human-review",
    )


def test_existing_render_is_bound_without_content_change() -> None:
    rendered = RenderedResult(
        kind=RendererKind.MARKDOWN,
        media_type="text/markdown",
        content="# Existing output\n",
        source_digest="digest",
        renderer_version="renderer-v1",
    )

    bound = bind_rendered_result(rendered, _binding())

    assert bound.content == rendered.content
    assert bound.binding.source_digest == rendered.source_digest


def test_binding_rejects_wrong_source_digest() -> None:
    rendered = RenderedResult(
        kind=RendererKind.JSON,
        media_type="application/json",
        content="{}\n",
        source_digest="actual",
        renderer_version="renderer-v1",
    )

    with pytest.raises(ValueError, match="source digest"):
        bind_rendered_result(rendered, _binding(digest="other"))


def test_binding_rejects_wrong_renderer_version() -> None:
    rendered = RenderedResult(
        kind=RendererKind.JSON,
        media_type="application/json",
        content="{}\n",
        source_digest="digest",
        renderer_version="actual-v1",
    )

    with pytest.raises(ValueError, match="renderer version"):
        bind_rendered_result(rendered, _binding(version="other-v1"))
