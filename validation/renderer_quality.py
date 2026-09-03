"""Measurable quality gates for final ReasoningRunResult presentation artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from reasoning.models import ReasoningRunResult
from renderer.contract import ReasoningRenderer, RendererKind

_FINAL_REPORT_KINDS = frozenset({RendererKind.JSON, RendererKind.MARKDOWN})


@dataclass(frozen=True, slots=True)
class RendererQualityMetrics:
    deterministic: bool
    source_binding: bool
    decision_visibility: bool
    artifact_coverage: float
    evidence_coverage: float
    epistemic_status_coverage: float
    open_question_coverage: float

    @property
    def perfect(self) -> bool:
        return (
            self.deterministic
            and self.source_binding
            and self.decision_visibility
            and self.artifact_coverage == 1.0
            and self.evidence_coverage == 1.0
            and self.epistemic_status_coverage == 1.0
            and self.open_question_coverage == 1.0
        )


@dataclass(frozen=True, slots=True)
class RendererQualityReport:
    renderer_kind: RendererKind
    renderer_version: str
    source_digest: str
    metrics: RendererQualityMetrics
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures and self.metrics.perfect

    def canonical_dict(self) -> dict[str, object]:
        return {
            "failures": list(self.failures),
            "metrics": asdict(self.metrics),
            "renderer_kind": self.renderer_kind.value,
            "renderer_version": self.renderer_version,
            "source_digest": self.source_digest,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _coverage(tokens: tuple[str, ...], content: str) -> float:
    unique = tuple(sorted(set(tokens)))
    if not unique:
        return 1.0
    present = sum(token in content for token in unique)
    return present / len(unique)


def _markdown_metrics(result: ReasoningRunResult, content: str) -> tuple[bool, float, float, float, float]:
    decision_tokens = [result.decision.outcome.value, result.decision.reason]
    if result.decision.artifact_id:
        decision_tokens.append(result.decision.artifact_id)
    decision_visible = all(token in content for token in decision_tokens)

    artifact_ids = tuple(item.artifact_id for item in result.artifacts)
    evidence_refs = tuple(
        evidence_ref
        for item in result.artifacts
        for evidence_ref in item.evidence_refs
    )
    statuses = tuple(item.status.value for item in result.artifacts)
    open_question_ids = tuple(item.question_id for item in result.open_questions)
    return (
        decision_visible,
        _coverage(artifact_ids, content),
        _coverage(evidence_refs, content),
        _coverage(statuses, content),
        _coverage(open_question_ids, content),
    )


def evaluate_reasoning_report(
    renderer: ReasoningRenderer,
    result: ReasoningRunResult,
) -> RendererQualityReport:
    """Render twice and fail closed unless the final report preserves reasoning traceability."""

    first = renderer.render(result)
    second = renderer.render(result)
    failures: list[str] = []

    deterministic = first == second
    if not deterministic:
        failures.append("NON_DETERMINISTIC_RENDER")

    expected_digest = result.digest()
    source_binding = first.source_digest == expected_digest
    if not source_binding:
        failures.append("SOURCE_BINDING_MISMATCH")

    if first.kind not in _FINAL_REPORT_KINDS:
        failures.append("NON_FINAL_REPORT_RENDERER")

    decision_visibility = False
    artifact_coverage = 0.0
    evidence_coverage = 0.0
    epistemic_status_coverage = 0.0
    open_question_coverage = 0.0

    if first.kind is RendererKind.JSON:
        try:
            parsed = json.loads(first.content)
        except json.JSONDecodeError:
            failures.append("INVALID_JSON_REPORT")
        else:
            canonical_match = parsed == result.canonical_dict()
            if not canonical_match:
                failures.append("CANONICAL_JSON_MISMATCH")
            decision_visibility = canonical_match
            artifact_coverage = 1.0 if canonical_match else 0.0
            evidence_coverage = 1.0 if canonical_match else 0.0
            epistemic_status_coverage = 1.0 if canonical_match else 0.0
            open_question_coverage = 1.0 if canonical_match else 0.0
    elif first.kind is RendererKind.MARKDOWN:
        (
            decision_visibility,
            artifact_coverage,
            evidence_coverage,
            epistemic_status_coverage,
            open_question_coverage,
        ) = _markdown_metrics(result, first.content)
        if expected_digest not in first.content:
            source_binding = False
            if "SOURCE_BINDING_MISMATCH" not in failures:
                failures.append("SOURCE_BINDING_MISMATCH")

    if not decision_visibility:
        failures.append("DECISION_NOT_VISIBLE")
    if artifact_coverage < 1.0:
        failures.append("ARTIFACT_COVERAGE_INCOMPLETE")
    if evidence_coverage < 1.0:
        failures.append("EVIDENCE_COVERAGE_INCOMPLETE")
    if epistemic_status_coverage < 1.0:
        failures.append("EPISTEMIC_STATUS_COVERAGE_INCOMPLETE")
    if open_question_coverage < 1.0:
        failures.append("OPEN_QUESTION_COVERAGE_INCOMPLETE")

    metrics = RendererQualityMetrics(
        deterministic=deterministic,
        source_binding=source_binding,
        decision_visibility=decision_visibility,
        artifact_coverage=artifact_coverage,
        evidence_coverage=evidence_coverage,
        epistemic_status_coverage=epistemic_status_coverage,
        open_question_coverage=open_question_coverage,
    )
    return RendererQualityReport(
        renderer_kind=first.kind,
        renderer_version=first.renderer_version,
        source_digest=first.source_digest,
        metrics=metrics,
        failures=tuple(sorted(set(failures))),
    )
