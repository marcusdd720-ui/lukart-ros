"""Bounded experiment contracts for learning candidates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from string import hexdigits

from learning.models import LearningCandidate, MetricValue

_ALLOWED_LEARNING_SPLITS = frozenset({"development", "validation"})
_HEX_DIGITS = frozenset(hexdigits.lower())


def _sha256_digest(name: str, value: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(character not in _HEX_DIGITS for character in digest):
        raise ValueError(f"{name} must be a SHA-256 digest")
    return digest


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


@dataclass(frozen=True, slots=True)
class MetricGuardrail:
    name: str
    direction: MetricDirection
    max_regression: float = 0.0

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("guardrail metric name cannot be blank")
        if not math.isfinite(self.max_regression) or self.max_regression < 0:
            raise ValueError("max_regression must be finite and non-negative")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True, slots=True)
class ExperimentContract:
    """An experiment is sandboxed and cannot use locked evaluation as tuning input."""

    experiment_id: str
    candidate_digest: str
    target_component: str
    baseline_revision: str
    candidate_revision: str
    sandbox_id: str
    allowed_splits: tuple[str, ...]
    guardrails: tuple[MetricGuardrail, ...]
    max_runs: int = 1

    def __post_init__(self) -> None:
        for field_name in (
            "experiment_id",
            "target_component",
            "baseline_revision",
            "candidate_revision",
            "sandbox_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} cannot be blank")
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "candidate_digest",
            _sha256_digest("candidate_digest", self.candidate_digest),
        )
        if self.baseline_revision == self.candidate_revision:
            raise ValueError("candidate revision must differ from baseline revision")
        if not self.allowed_splits:
            raise ValueError("experiment requires at least one allowed split")
        normalized_splits = tuple(split.strip() for split in self.allowed_splits)
        if not all(normalized_splits):
            raise ValueError("experiment split cannot be blank")
        unsupported = sorted(set(normalized_splits) - _ALLOWED_LEARNING_SPLITS)
        if unsupported:
            raise ValueError(f"unsupported learning experiment split(s): {', '.join(unsupported)}")
        if len(normalized_splits) != len(set(normalized_splits)):
            raise ValueError("experiment splits must be unique")
        if not self.guardrails:
            raise ValueError("experiment requires measurable guardrails")
        names = [guardrail.name for guardrail in self.guardrails]
        if len(names) != len(set(names)):
            raise ValueError("experiment guardrail metrics must be unique")
        if self.max_runs < 1:
            raise ValueError("max_runs must be >= 1")
        object.__setattr__(self, "allowed_splits", normalized_splits)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "allowed_splits": list(self.allowed_splits),
            "baseline_revision": self.baseline_revision,
            "candidate_digest": self.candidate_digest,
            "candidate_revision": self.candidate_revision,
            "experiment_id": self.experiment_id,
            "guardrails": [
                {
                    "direction": guardrail.direction.value,
                    "max_regression": guardrail.max_regression,
                    "name": guardrail.name,
                }
                for guardrail in self.guardrails
            ],
            "max_runs": self.max_runs,
            "sandbox_id": self.sandbox_id,
            "target_component": self.target_component,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ExperimentMeasurement:
    revision: str
    metrics: tuple[MetricValue, ...]

    def __post_init__(self) -> None:
        revision = self.revision.strip()
        if not revision:
            raise ValueError("measurement revision cannot be blank")
        if not self.metrics:
            raise ValueError("experiment measurement requires metrics")
        names = [metric.name for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("experiment measurement metrics must be unique")
        object.__setattr__(self, "revision", revision)

    def metric_map(self) -> dict[str, float]:
        return {metric.name: metric.value for metric in self.metrics}


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    contract_digest: str
    baseline: ExperimentMeasurement
    candidate: ExperimentMeasurement
    run_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contract_digest",
            _sha256_digest("contract_digest", self.contract_digest),
        )
        if self.run_count < 1:
            raise ValueError("run_count must be >= 1")


def contract_for_candidate(
    candidate: LearningCandidate,
    *,
    experiment_id: str,
    baseline_revision: str,
    candidate_revision: str,
    sandbox_id: str,
    allowed_splits: tuple[str, ...],
    guardrails: tuple[MetricGuardrail, ...],
    max_runs: int = 1,
) -> ExperimentContract:
    return ExperimentContract(
        experiment_id=experiment_id,
        candidate_digest=candidate.digest(),
        target_component=candidate.target_component,
        baseline_revision=baseline_revision,
        candidate_revision=candidate_revision,
        sandbox_id=sandbox_id,
        allowed_splits=allowed_splits,
        guardrails=guardrails,
        max_runs=max_runs,
    )
