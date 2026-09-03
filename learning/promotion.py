"""Promotion eligibility decisions for measured learning experiments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from learning.experiment import ExperimentContract, ExperimentResult, MetricDirection


class PromotionStatus(StrEnum):
    ELIGIBLE_FOR_PROMOTION = "eligible_for_promotion"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class MetricDelta:
    name: str
    baseline: float
    candidate: float
    signed_improvement: float
    allowed_regression: float


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Decision artifact only; it has no authority to mutate canonical state."""

    status: PromotionStatus
    reason: str
    contract_digest: str
    deltas: tuple[MetricDelta, ...]


class PromotionGate:
    """Fail-closed metric gate for candidate eligibility."""

    def evaluate(
        self,
        contract: ExperimentContract,
        result: ExperimentResult,
    ) -> PromotionDecision:
        contract_digest = contract.digest()
        if result.contract_digest != contract_digest:
            return PromotionDecision(
                status=PromotionStatus.REJECTED,
                reason="experiment result is not bound to this contract",
                contract_digest=contract_digest,
                deltas=(),
            )
        if result.baseline.revision != contract.baseline_revision:
            return PromotionDecision(
                status=PromotionStatus.REJECTED,
                reason="baseline revision does not match experiment contract",
                contract_digest=contract_digest,
                deltas=(),
            )
        if result.candidate.revision != contract.candidate_revision:
            return PromotionDecision(
                status=PromotionStatus.REJECTED,
                reason="candidate revision does not match experiment contract",
                contract_digest=contract_digest,
                deltas=(),
            )
        if result.run_count > contract.max_runs:
            return PromotionDecision(
                status=PromotionStatus.REJECTED,
                reason="experiment exceeded contracted run budget",
                contract_digest=contract_digest,
                deltas=(),
            )

        baseline = result.baseline.metric_map()
        candidate = result.candidate.metric_map()
        deltas: list[MetricDelta] = []
        improved = False

        for guardrail in contract.guardrails:
            if guardrail.name not in baseline or guardrail.name not in candidate:
                return PromotionDecision(
                    status=PromotionStatus.REJECTED,
                    reason=f"missing required metric: {guardrail.name}",
                    contract_digest=contract_digest,
                    deltas=tuple(deltas),
                )

            before = baseline[guardrail.name]
            after = candidate[guardrail.name]
            if guardrail.direction is MetricDirection.HIGHER_IS_BETTER:
                signed_improvement = after - before
            else:
                signed_improvement = before - after

            deltas.append(
                MetricDelta(
                    name=guardrail.name,
                    baseline=before,
                    candidate=after,
                    signed_improvement=signed_improvement,
                    allowed_regression=guardrail.max_regression,
                )
            )
            if signed_improvement < -guardrail.max_regression:
                return PromotionDecision(
                    status=PromotionStatus.REJECTED,
                    reason=f"metric regression exceeds guardrail: {guardrail.name}",
                    contract_digest=contract_digest,
                    deltas=tuple(deltas),
                )
            if signed_improvement > 0:
                improved = True

        if not improved:
            return PromotionDecision(
                status=PromotionStatus.INCONCLUSIVE,
                reason="candidate has no measured improvement",
                contract_digest=contract_digest,
                deltas=tuple(deltas),
            )

        return PromotionDecision(
            status=PromotionStatus.ELIGIBLE_FOR_PROMOTION,
            reason="candidate improved at least one metric without guardrail violation",
            contract_digest=contract_digest,
            deltas=tuple(deltas),
        )
