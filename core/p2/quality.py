"""P2 longitudinal quality intelligence, explainability and Gold candidate discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence

from reasoning.models import ReasoningRunResult


class MetricDirection(StrEnum):
    MIN = "min"
    MAX = "max"


class TrendStatus(StrEnum):
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    STABLE = "STABLE"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class QualityObservation:
    version: str
    metrics: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class MetricTrend:
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    status: TrendStatus


class QualityTrendAnalyzer:
    def __init__(self, directions: Mapping[str, MetricDirection | str]) -> None:
        self._directions = {
            metric: MetricDirection(direction) for metric, direction in directions.items()
        }

    def compare(
        self, baseline: QualityObservation, current: QualityObservation
    ) -> tuple[MetricTrend, ...]:
        trends: list[MetricTrend] = []
        for metric in sorted(self._directions):
            left = baseline.metrics.get(metric)
            right = current.metrics.get(metric)
            if left is None or right is None:
                trends.append(MetricTrend(metric, left, right, None, TrendStatus.MISSING))
                continue
            delta = right - left
            if delta == 0:
                status = TrendStatus.STABLE
            else:
                direction = self._directions[metric]
                improved = delta > 0 if direction is MetricDirection.MIN else delta < 0
                status = TrendStatus.IMPROVED if improved else TrendStatus.REGRESSED
            trends.append(MetricTrend(metric, left, right, delta, status))
        return tuple(trends)


@dataclass(frozen=True, slots=True)
class ExplainabilityReport:
    outcome: str
    conclusion_artifact_id: str | None
    support_lineage: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    open_questions: tuple[str, ...]
    decisive_factors: tuple[str, ...]
    counterfactual_checks: tuple[str, ...]


def explain_result(result: ReasoningRunResult) -> ExplainabilityReport:
    by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}
    conclusion_id = result.decision.artifact_id
    lineage: set[str] = set()
    pending = [conclusion_id] if conclusion_id else []
    while pending:
        current = pending.pop()
        if current is None or current in lineage or current not in by_id:
            continue
        lineage.add(current)
        pending.extend(by_id[current].support_ids)

    evidence = sorted(
        {
            evidence_ref
            for artifact_id in lineage
            for evidence_ref in by_id[artifact_id].evidence_refs
        }
    )
    factors = tuple(
        f"{artifact_id}:{by_id[artifact_id].status.value}"
        for artifact_id in sorted(lineage)
    )
    counterfactuals = tuple(
        f"Revalidate if {artifact_id} changes status, support, or evidence lineage."
        for artifact_id in sorted(lineage)
        if artifact_id != conclusion_id
    )
    questions = tuple(
        f"{question.question_id}:{question.question}"
        for question in sorted(result.open_questions, key=lambda item: item.question_id)
    )
    return ExplainabilityReport(
        outcome=result.decision.outcome.value,
        conclusion_artifact_id=conclusion_id,
        support_lineage=tuple(sorted(lineage)),
        evidence_refs=tuple(evidence),
        open_questions=questions,
        decisive_factors=factors,
        counterfactual_checks=counterfactuals,
    )


class FailureSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_SEVERITY_RANK = {
    FailureSeverity.LOW: 1,
    FailureSeverity.MEDIUM: 2,
    FailureSeverity.HIGH: 3,
    FailureSeverity.CRITICAL: 4,
}


@dataclass(frozen=True, slots=True)
class FailureEvent:
    signature: str
    severity: FailureSeverity
    case_id: str
    synthetic_or_anonymized: bool
    details: str = ""


@dataclass(frozen=True, slots=True)
class GoldCandidate:
    signature: str
    occurrences: int
    max_severity: FailureSeverity
    case_ids: tuple[str, ...]
    rationale: str
    promotion_state: str = field(default="CANDIDATE", init=False)


def discover_gold_candidates(
    events: Sequence[FailureEvent],
    *,
    min_occurrences: int = 2,
    min_severity: FailureSeverity = FailureSeverity.MEDIUM,
) -> tuple[GoldCandidate, ...]:
    grouped: dict[str, list[FailureEvent]] = {}
    for event in events:
        if not event.synthetic_or_anonymized:
            continue
        grouped.setdefault(event.signature.strip(), []).append(event)

    candidates: list[GoldCandidate] = []
    for signature, items in sorted(grouped.items()):
        if not signature or len(items) < min_occurrences:
            continue
        maximum = max(items, key=lambda item: _SEVERITY_RANK[item.severity]).severity
        if _SEVERITY_RANK[maximum] < _SEVERITY_RANK[min_severity]:
            continue
        case_ids = tuple(sorted({item.case_id for item in items}))
        candidates.append(
            GoldCandidate(
                signature=signature,
                occurrences=len(items),
                max_severity=maximum,
                case_ids=case_ids,
                rationale="Repeated validated failure pattern; independent review required before Gold.",
            )
        )
    return tuple(candidates)
