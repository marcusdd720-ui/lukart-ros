"""P3-04..P3-06 operational integration: dossier, KQM history, experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from core.p2.quality import ExplainabilityReport, explain_result
from reasoning.models import ReasoningRunResult

from .contracts import P3ContractError, TrustLevel, content_digest


@dataclass(frozen=True, slots=True)
class ExplainabilityDossier:
    schema: str
    source_reasoning_digest: str
    outcome: str
    conclusion_artifact_id: str | None
    support_lineage: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    open_questions: tuple[str, ...]
    contradictions: tuple[str, ...]
    decisive_factors: tuple[str, ...]
    counterfactual_checks: tuple[str, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_reasoning_digest": self.source_reasoning_digest,
            "outcome": self.outcome,
            "conclusion_artifact_id": self.conclusion_artifact_id,
            "support_lineage": list(self.support_lineage),
            "evidence_refs": list(self.evidence_refs),
            "open_questions": list(self.open_questions),
            "contradictions": list(self.contradictions),
            "decisive_factors": list(self.decisive_factors),
            "counterfactual_checks": list(self.counterfactual_checks),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def build_explainability_dossier(
    result: ReasoningRunResult,
    *,
    contradictions: Sequence[str] = (),
) -> ExplainabilityDossier:
    """Project P2 explainability into a source-bound final dossier contract."""

    report: ExplainabilityReport = explain_result(result)
    normalized_contradictions = tuple(
        sorted({item.strip() for item in contradictions if item.strip()})
    )
    return ExplainabilityDossier(
        schema="lukart.explainability-dossier.v1",
        source_reasoning_digest=result.digest(),
        outcome=report.outcome,
        conclusion_artifact_id=report.conclusion_artifact_id,
        support_lineage=report.support_lineage,
        evidence_refs=report.evidence_refs,
        open_questions=report.open_questions,
        contradictions=normalized_contradictions,
        decisive_factors=report.decisive_factors,
        counterfactual_checks=report.counterfactual_checks,
    )


class MetricObjective(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class QualityDirection(StrEnum):
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    STABLE = "STABLE"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class QualityPoint:
    release_id: str
    code_sha: str
    corpus_digest: str
    metrics: Mapping[str, float]

    def __post_init__(self) -> None:
        identities = (self.release_id, self.code_sha, self.corpus_digest)
        if any(not identity.strip() for identity in identities):
            raise P3ContractError("quality point identity cannot be blank")
        for metric, value in self.metrics.items():
            if not metric.strip():
                raise P3ContractError("quality metric name cannot be blank")
            if not isinstance(value, int | float):
                raise P3ContractError("quality metric values must be numeric")

    def digest(self) -> str:
        return content_digest(
            {
                "release_id": self.release_id,
                "code_sha": self.code_sha,
                "corpus_digest": self.corpus_digest,
                "metrics": dict(self.metrics),
            }
        )


@dataclass(frozen=True, slots=True)
class QualityDelta:
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    direction: QualityDirection


class LongitudinalQualityStore:
    """Append-only logical quality history with unambiguous optimization goals."""

    def __init__(self, objectives: Mapping[str, MetricObjective | str]) -> None:
        self._objectives = {
            metric: MetricObjective(objective) for metric, objective in objectives.items()
        }
        if not self._objectives or any(not metric.strip() for metric in self._objectives):
            raise P3ContractError("quality objectives are required")
        self._points: list[QualityPoint] = []

    def append(self, point: QualityPoint) -> None:
        if any(existing.release_id == point.release_id for existing in self._points):
            raise P3ContractError(f"duplicate quality release_id: {point.release_id}")
        self._points.append(point)

    def points(self) -> tuple[QualityPoint, ...]:
        return tuple(self._points)

    def compare(
        self, baseline_release: str, current_release: str
    ) -> tuple[QualityDelta, ...]:
        by_release = {point.release_id: point for point in self._points}
        if baseline_release not in by_release or current_release not in by_release:
            raise P3ContractError("quality comparison references unknown release")
        baseline = by_release[baseline_release]
        current = by_release[current_release]
        result: list[QualityDelta] = []
        for metric, objective in sorted(self._objectives.items()):
            left = baseline.metrics.get(metric)
            right = current.metrics.get(metric)
            if left is None or right is None:
                result.append(QualityDelta(metric, left, right, None, QualityDirection.MISSING))
                continue
            delta = right - left
            if delta == 0:
                direction = QualityDirection.STABLE
            else:
                improved = (
                    delta > 0
                    if objective is MetricObjective.HIGHER_IS_BETTER
                    else delta < 0
                )
                direction = QualityDirection.IMPROVED if improved else QualityDirection.REGRESSED
            result.append(QualityDelta(metric, left, right, delta, direction))
        return tuple(result)


class ExperimentState(StrEnum):
    FAILURE = "FAILURE"
    CANDIDATE = "CANDIDATE"
    EXPERIMENT = "EXPERIMENT"
    VALIDATION = "VALIDATION"
    PROMOTION = "PROMOTION"
    MONITORING = "MONITORING"
    ROLLED_BACK = "ROLLED_BACK"


_ALLOWED_TRANSITIONS: Mapping[ExperimentState, frozenset[ExperimentState]] = {
    ExperimentState.FAILURE: frozenset({ExperimentState.CANDIDATE}),
    ExperimentState.CANDIDATE: frozenset({ExperimentState.EXPERIMENT}),
    ExperimentState.EXPERIMENT: frozenset({ExperimentState.VALIDATION}),
    ExperimentState.VALIDATION: frozenset({ExperimentState.PROMOTION}),
    ExperimentState.PROMOTION: frozenset({ExperimentState.MONITORING}),
    ExperimentState.MONITORING: frozenset({ExperimentState.ROLLED_BACK}),
    ExperimentState.ROLLED_BACK: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ControlledExperiment:
    experiment_id: str
    state: ExperimentState
    candidate_digest: str
    validation_digest: str | None = None
    approver_id: str | None = None
    trust_level: TrustLevel = TrustLevel.CANDIDATE
    audit_events: tuple[str, ...] = ()


class ControlledExperimentManager:
    """Fail-closed experiment lifecycle; no autonomous candidate->trusted path."""

    def transition(
        self,
        experiment: ControlledExperiment,
        target: ExperimentState,
        *,
        validation_digest: str | None = None,
        approver_id: str | None = None,
    ) -> ControlledExperiment:
        if target not in _ALLOWED_TRANSITIONS[experiment.state]:
            raise P3ContractError(
                f"illegal experiment transition: {experiment.state.value}->{target.value}"
            )
        next_validation = validation_digest or experiment.validation_digest
        next_approver = approver_id or experiment.approver_id
        trust = experiment.trust_level
        if target is ExperimentState.PROMOTION:
            if not next_validation or not next_validation.strip():
                raise P3ContractError("promotion requires validation digest")
            if not next_approver or not next_approver.strip():
                raise P3ContractError("promotion requires explicit approver identity")
            trust = TrustLevel.VALIDATED
        elif target is ExperimentState.MONITORING:
            if experiment.state is not ExperimentState.PROMOTION:
                raise P3ContractError("monitoring requires prior promotion")
            trust = TrustLevel.TRUSTED
        elif target is ExperimentState.ROLLED_BACK:
            trust = TrustLevel.CANDIDATE

        event = f"{experiment.state.value}->{target.value}"
        return replace(
            experiment,
            state=target,
            validation_digest=next_validation,
            approver_id=next_approver,
            trust_level=trust,
            audit_events=(*experiment.audit_events, event),
        )
