"""Measured certification policy for controlled agents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from agents.contract import AgentContract
from validation.extraction_quality import ExtractionMetrics
from validation.independent_evaluation import ReviewOutcome
from validation.measurement import MeasurementCollector, MeasurementSnapshot


class AgentCertificationStatus(StrEnum):
    EVALUATED = "evaluated"
    PENDING_EXTERNAL_REVIEW = "pending_external_review"
    CERTIFIED = "certified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AgentCertificationThresholds:
    min_precision: float
    min_recall: float
    min_f1: float
    min_critical_recall: float
    min_provenance_completeness: float = 1.0
    max_critical_fact_loss: int = 0
    max_case_number_false_positive_rate: float = 0.0

    def __post_init__(self) -> None:
        bounded = (
            self.min_precision,
            self.min_recall,
            self.min_f1,
            self.min_critical_recall,
            self.min_provenance_completeness,
            self.max_case_number_false_positive_rate,
        )
        if any(not 0.0 <= value <= 1.0 for value in bounded):
            raise ValueError("certification rate thresholds must be between 0 and 1")
        if self.max_critical_fact_loss < 0:
            raise ValueError("max_critical_fact_loss must be >= 0")


@dataclass(frozen=True, slots=True)
class AgentCertificationReport:
    agent_name: str
    agent_version: str
    contract_sha256: str
    corpus_version: str
    split_name: str
    measurements: MeasurementSnapshot
    status: AgentCertificationStatus
    failures: tuple[str, ...]
    external_review: ReviewOutcome


class AgentCertifier:
    """Convert measured KQM results into an explicit certification decision."""

    def __init__(
        self,
        thresholds: AgentCertificationThresholds,
        *,
        require_independent_review: bool = True,
    ) -> None:
        self.thresholds = thresholds
        self.require_independent_review = require_independent_review
        self.measurements = MeasurementCollector()

    def evaluate(
        self,
        contract: AgentContract,
        metrics: ExtractionMetrics,
        *,
        corpus_version: str,
        split_name: str,
        external_review: ReviewOutcome = ReviewOutcome.PENDING,
    ) -> AgentCertificationReport:
        failures = self._threshold_failures(metrics)
        if failures or external_review is ReviewOutcome.FAIL:
            status = AgentCertificationStatus.REJECTED
        elif self.require_independent_review and external_review is not ReviewOutcome.PASS:
            status = AgentCertificationStatus.PENDING_EXTERNAL_REVIEW
        elif external_review is ReviewOutcome.PASS or not self.require_independent_review:
            status = AgentCertificationStatus.CERTIFIED
        else:
            status = AgentCertificationStatus.EVALUATED

        if external_review is ReviewOutcome.FAIL:
            failures = (*failures, "independent review failed")

        return AgentCertificationReport(
            agent_name=contract.name,
            agent_version=contract.version,
            contract_sha256=contract_sha256(contract),
            corpus_version=corpus_version,
            split_name=split_name,
            measurements=self.measurements.from_extraction(metrics),
            status=status,
            failures=failures,
            external_review=external_review,
        )

    def _threshold_failures(self, metrics: ExtractionMetrics) -> tuple[str, ...]:
        checks = (
            (metrics.precision >= self.thresholds.min_precision, "precision below threshold"),
            (metrics.recall >= self.thresholds.min_recall, "recall below threshold"),
            (metrics.f1 >= self.thresholds.min_f1, "f1 below threshold"),
            (
                metrics.critical_recall >= self.thresholds.min_critical_recall,
                "critical_recall below threshold",
            ),
            (
                metrics.provenance_completeness
                >= self.thresholds.min_provenance_completeness,
                "provenance_completeness below threshold",
            ),
            (
                metrics.critical_fact_loss <= self.thresholds.max_critical_fact_loss,
                "critical_fact_loss above threshold",
            ),
            (
                metrics.case_number_false_positive_rate
                <= self.thresholds.max_case_number_false_positive_rate,
                "case_number_false_positive_rate above threshold",
            ),
        )
        return tuple(message for passed, message in checks if not passed)


def contract_sha256(contract: AgentContract) -> str:
    """Return a deterministic fingerprint of certification-relevant contract fields."""

    payload = {
        "agent_id": str(contract.agent_id),
        "name": contract.name,
        "version": contract.version,
        "input_schema": contract.input_schema,
        "output_schema": contract.output_schema,
        "required_evidence_types": list(contract.required_evidence_types),
        "allowed_operations": list(contract.allowed_operations),
        "forbidden_operations": list(contract.forbidden_operations),
        "allowed_epistemic_statuses": [
            status.value for status in contract.allowed_epistemic_statuses
        ],
        "validation_gates": list(contract.validation_gates),
        "resource_limits": {
            "max_runtime_seconds": contract.resource_limits.max_runtime_seconds,
            "max_model_calls": contract.resource_limits.max_model_calls,
            "max_cost_units": contract.resource_limits.max_cost_units,
        },
        "provenance_required": contract.provenance_required,
        "deterministic": contract.deterministic,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
