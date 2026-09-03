from __future__ import annotations

from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact
from renderer import (
    EvidenceListRenderer,
    JsonReasoningRenderer,
    MarkdownReasoningRenderer,
    RenderedResult,
    RendererKind,
)
from validation.renderer_quality import evaluate_reasoning_report


def _conclusion_result():  # type: ignore[no-untyped-def]
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
    return ReasoningEngine((fact, conclusion)).evaluate("C1")


def _abstention_result():  # type: ignore[no-untyped-def]
    unknown = ReasoningArtifact(
        artifact_id="U1",
        statement="Synthetic value is unknown.",
        status=KnowledgeStatus.UNKNOWN,
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Synthetic value is established.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("U1",),
    )
    return ReasoningEngine((unknown, conclusion)).evaluate("C1")


def test_json_and_markdown_final_reports_pass_quality_gate() -> None:
    result = _conclusion_result()

    json_report = evaluate_reasoning_report(JsonReasoningRenderer(), result)
    markdown_report = evaluate_reasoning_report(MarkdownReasoningRenderer(), result)

    assert json_report.passed is True
    assert markdown_report.passed is True
    assert len(json_report.digest()) == 64
    assert len(markdown_report.digest()) == 64


def test_abstention_report_must_preserve_open_questions() -> None:
    result = _abstention_result()
    report = evaluate_reasoning_report(MarkdownReasoningRenderer(), result)

    assert result.open_questions
    assert report.passed is True
    assert report.metrics.open_question_coverage == 1.0


def test_evidence_list_is_not_accepted_as_final_report() -> None:
    result = _conclusion_result()
    report = evaluate_reasoning_report(EvidenceListRenderer(), result)

    assert report.passed is False
    assert "NON_FINAL_REPORT_RENDERER" in report.failures


class _LossyMarkdownRenderer:
    kind = RendererKind.MARKDOWN
    version = "lossy-markdown-v1"

    def render(self, result):  # type: ignore[no-untyped-def]
        return RenderedResult(
            kind=self.kind,
            media_type="text/markdown; charset=utf-8",
            content="# Summary only\n",
            source_digest=result.digest(),
            renderer_version=self.version,
        )


def test_lossy_final_report_fails_traceability_gate() -> None:
    report = evaluate_reasoning_report(_LossyMarkdownRenderer(), _conclusion_result())

    assert report.passed is False
    assert "DECISION_NOT_VISIBLE" in report.failures
    assert "ARTIFACT_COVERAGE_INCOMPLETE" in report.failures
    assert "EVIDENCE_COVERAGE_INCOMPLETE" in report.failures
    assert "EPISTEMIC_STATUS_COVERAGE_INCOMPLETE" in report.failures
