from __future__ import annotations

import json

import pytest

from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact
from renderer import (
    EvidenceListRenderer,
    JsonReasoningRenderer,
    MarkdownReasoningRenderer,
    RendererKind,
    RendererRegistry,
)


def _result():  # type: ignore[no-untyped-def]
    fact = ReasoningArtifact(
        artifact_id="F1",
        statement="Synthetic fact.",
        status=KnowledgeStatus.FACT,
        evidence_refs=("SYN-E-1",),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Synthetic conclusion.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("F1",),
    )
    return ReasoningEngine((conclusion, fact)).evaluate("C1")


def test_json_renderer_preserves_canonical_reasoning_result() -> None:
    result = _result()
    rendered = JsonReasoningRenderer().render(result)

    assert rendered.kind is RendererKind.JSON
    assert rendered.source_digest == result.digest()
    assert json.loads(rendered.content) == result.canonical_dict()


def test_markdown_renderer_is_deterministic_and_exposes_provenance() -> None:
    result = _result()
    renderer = MarkdownReasoningRenderer()

    first = renderer.render(result)
    second = renderer.render(result)

    assert first == second
    assert "**CONCLUDE**" in first.content
    assert "SYN-E-1" in first.content
    assert result.digest() in first.content


def test_evidence_list_renderer_maps_sources_to_artifacts() -> None:
    result = _result()
    rendered = EvidenceListRenderer().render(result)
    payload = json.loads(rendered.content)

    assert payload["source_digest"] == result.digest()
    assert payload["evidence"] == [
        {
            "artifact_ids": ["F1"],
            "evidence_ref": "SYN-E-1",
            "statuses": ["FACT"],
        }
    ]


def test_renderer_registry_fails_closed_on_duplicate_kind() -> None:
    registry = RendererRegistry()
    registry.register(JsonReasoningRenderer())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(JsonReasoningRenderer())

    assert registry.require(RendererKind.JSON).version == "reasoning-json-v1"
    with pytest.raises(KeyError, match="not registered"):
        registry.require(RendererKind.MARKDOWN)
