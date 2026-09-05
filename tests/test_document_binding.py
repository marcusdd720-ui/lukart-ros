import pytest

from knowledge.models.document_binding import (
    ArtifactRef,
    BoundRenderedDocument,
    DocumentBinding,
    DocumentStatus,
)


def _ref(kind: str, identity: str, version: int = 1) -> ArtifactRef:
    return ArtifactRef(kind, identity, version, f"digest-{kind}-{identity}-{version}")


def test_document_binding_records_exact_upstream_artifacts() -> None:
    refs = (
        _ref("case_model", "CASE-001", 2),
        _ref("problem", "PROBLEM-1", 3),
        _ref("decision", "DEC-1", 2),
        _ref("strategy", "STRAT-1", 1),
        _ref("plan", "PLAN-1", 1),
    )
    binding = DocumentBinding(
        document_id="DOC-1",
        renderer_id="markdown",
        renderer_version="v1",
        template_id="legal-dossier",
        template_version="v1",
        input_refs=refs,
        source_digest="source-digest",
        generated_at="2026-09-05T04:20:00Z",
        communication_target="human-review",
        unresolved_refs=("OPEN-1",),
        contradiction_refs=("CONTRA-1",),
        limitation_refs=("LIMIT-1",),
    )

    assert binding.input_refs == refs
    assert binding.unresolved_refs == ("OPEN-1",)


def test_template_cannot_manufacture_missing_content() -> None:
    binding = DocumentBinding(
        document_id="DOC-1",
        renderer_id="markdown",
        renderer_version="v1",
        template_id="template",
        template_version="v1",
        input_refs=(),
        source_digest="digest",
        generated_at="2026-09-05T04:20:00Z",
        communication_target="client",
        required_sections=("facts", "unsupported-new-legal-conclusion"),
    )

    with pytest.raises(ValueError, match="unsupported upstream content"):
        binding.require_supported_sections(("facts",))


def test_high_risk_document_requires_review_state() -> None:
    with pytest.raises(ValueError, match="REVIEW_REQUIRED"):
        DocumentBinding(
            document_id="DOC-1",
            renderer_id="markdown",
            renderer_version="v1",
            template_id="filing",
            template_version="v1",
            input_refs=(),
            source_digest="digest",
            generated_at="2026-09-05T04:20:00Z",
            communication_target="court",
            approval_required=True,
            status=DocumentStatus.DRAFT,
        )


def test_approved_high_risk_document_requires_approval_record() -> None:
    with pytest.raises(ValueError, match="human approval"):
        DocumentBinding(
            document_id="DOC-1",
            renderer_id="markdown",
            renderer_version="v1",
            template_id="filing",
            template_version="v1",
            input_refs=(),
            source_digest="digest",
            generated_at="2026-09-05T04:20:00Z",
            communication_target="court",
            approval_required=True,
            status=DocumentStatus.APPROVED,
        )


def test_review_required_document_can_be_rendered_without_authorizing_execution() -> None:
    binding = DocumentBinding(
        document_id="DOC-1",
        renderer_id="markdown",
        renderer_version="v1",
        template_id="filing",
        template_version="v1",
        input_refs=(_ref("plan", "PLAN-1"),),
        source_digest="digest",
        generated_at="2026-09-05T04:20:00Z",
        communication_target="court",
        approval_required=True,
        status=DocumentStatus.REVIEW_REQUIRED,
    )
    rendered = BoundRenderedDocument(binding, "text/markdown", "# Draft\n")

    assert rendered.binding.status is DocumentStatus.REVIEW_REQUIRED
