"""KQM-03 identity-preserving longitudinal quality measurement.

Longitudinal KQM is a derived measurement surface only. It preserves the exact
PHX-02 evaluation identity and candidate runtime identity and never mutates
Gold, Product state, the Canonical Case Ledger, or release authorization state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import cast

from core.case_ledger import ContentAddress, DigestAlgorithm
from core.p3.contracts import P3ContractError, RuntimeIdentity
from core.p3.ledger import AppendOnlyReplayLedger

from .contracts import (
    EvaluationContractError,
    EvaluationInputIdentity,
    EvaluatorIdentity,
    KQMPolicy,
    KQMProjection,
    MetricDirection,
)

KQM_LONGITUDINAL_POINT_SCHEMA_V1 = "lukart.kqm-longitudinal-point.v1"
KQM_LONGITUDINAL_COMPARISON_SCHEMA_V1 = "lukart.kqm-longitudinal-comparison.v1"


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise EvaluationContractError(
            f"{field_name} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise EvaluationContractError(
            f"{field_name} cannot contain control characters"
        )
    return value


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise EvaluationContractError(f"{field_name} must be an object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except P3ContractError as exc:
        raise EvaluationContractError(str(exc)) from exc


def _finite_metrics(value: Mapping[str, float]) -> Mapping[str, float]:
    normalized: dict[str, float] = {}
    for name, raw in value.items():
        metric_name = _identifier(name, field_name="metric name")
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise EvaluationContractError(
                f"metric {metric_name} must be numeric"
            )
        metric_value = float(raw)
        if not math.isfinite(metric_value):
            raise EvaluationContractError(
                f"metric {metric_name} must be finite"
            )
        normalized[metric_name] = metric_value
    return MappingProxyType(dict(sorted(normalized.items())))


class KQMDeltaDirection(StrEnum):
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    STABLE = "STABLE"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class KQMMetricDelta:
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    direction: KQMDeltaDirection

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric",
            _identifier(self.metric, field_name="metric"),
        )
        for name, value in (
            ("baseline", self.baseline),
            ("current", self.current),
            ("delta", self.delta),
        ):
            if value is not None and not math.isfinite(value):
                raise EvaluationContractError(
                    f"{name} must be finite when present"
                )
        if self.direction is KQMDeltaDirection.MISSING:
            if self.delta is not None or (
                self.baseline is not None and self.current is not None
            ):
                raise EvaluationContractError(
                    "MISSING delta must have an absent side and no delta"
                )
        elif (
            self.baseline is None
            or self.current is None
            or self.delta is None
        ):
            raise EvaluationContractError(
                "non-MISSING delta requires baseline, current and delta"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "current": self.current,
            "delta": self.delta,
            "direction": self.direction.value,
        }


@dataclass(frozen=True, slots=True)
class KQMLongitudinalPoint:
    release_id: str
    comparison_context_identity: ContentAddress
    input_identity: ContentAddress
    corpus_identity: ContentAddress
    policy_identity: ContentAddress
    evaluator_identity: ContentAddress
    candidate_runtime_identity: ContentAddress
    projection_identity: ContentAddress
    metrics: Mapping[str, float]
    projection_passed: bool
    projection_failures: tuple[str, ...]
    point_identity: ContentAddress
    schema: str = KQM_LONGITUDINAL_POINT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != KQM_LONGITUDINAL_POINT_SCHEMA_V1:
            raise EvaluationContractError(
                f"unsupported longitudinal point schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "release_id",
            _identifier(self.release_id, field_name="release_id"),
        )
        object.__setattr__(self, "metrics", _finite_metrics(self.metrics))
        failures = tuple(
            _identifier(item, field_name="projection failure")
            for item in self.projection_failures
        )
        if tuple(sorted(failures)) != failures:
            raise EvaluationContractError(
                "projection failures must be sorted"
            )
        if len(set(failures)) != len(failures):
            raise EvaluationContractError(
                "projection failures must be unique"
            )
        if self.projection_passed != (not failures):
            raise EvaluationContractError(
                "projection_passed must match projection_failures"
            )
        object.__setattr__(self, "projection_failures", failures)
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        release_id: str,
        evaluation_input: EvaluationInputIdentity,
        policy: KQMPolicy,
        evaluator: EvaluatorIdentity,
        candidate_runtime: RuntimeIdentity,
        projection: KQMProjection,
    ) -> KQMLongitudinalPoint:
        if not candidate_runtime.complete_for_replay:
            missing = ", ".join(candidate_runtime.incomplete_fields())
            raise EvaluationContractError(
                f"candidate runtime identity is incomplete: {missing}"
            )
        if evaluation_input.policy_identity != policy.policy_identity:
            raise EvaluationContractError(
                "evaluation input policy identity mismatch"
            )
        if evaluation_input.evaluator_identity != evaluator.evaluator_identity:
            raise EvaluationContractError(
                "evaluation input evaluator identity mismatch"
            )
        if projection.input_identity != evaluation_input.input_identity:
            raise EvaluationContractError("projection input identity mismatch")
        if projection.policy_identity != policy.policy_identity:
            raise EvaluationContractError("projection policy identity mismatch")
        if projection.evaluator_identity != evaluator.evaluator_identity:
            raise EvaluationContractError(
                "projection evaluator identity mismatch"
            )

        runtime_identity = ContentAddress(
            algorithm=DigestAlgorithm.SHA256,
            digest=candidate_runtime.digest(),
        )
        body = cls._body(
            release_id=release_id,
            comparison_context_identity=evaluation_input.input_identity,
            input_identity=evaluation_input.input_identity,
            corpus_identity=evaluation_input.corpus_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            candidate_runtime_identity=runtime_identity,
            projection_identity=projection.projection_identity,
            metrics=projection.metrics,
            projection_passed=projection.passed,
            projection_failures=projection.failures,
        )
        return cls(
            release_id=release_id,
            comparison_context_identity=evaluation_input.input_identity,
            input_identity=evaluation_input.input_identity,
            corpus_identity=evaluation_input.corpus_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            candidate_runtime_identity=runtime_identity,
            projection_identity=projection.projection_identity,
            metrics=projection.metrics,
            projection_passed=projection.passed,
            projection_failures=projection.failures,
            point_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> KQMLongitudinalPoint:
        expected = {
            "schema",
            "release_id",
            "comparison_context_identity",
            "input_identity",
            "corpus_identity",
            "policy_identity",
            "evaluator_identity",
            "candidate_runtime_identity",
            "projection_identity",
            "metrics",
            "projection_passed",
            "projection_failures",
            "point_identity",
        }
        if set(value) != expected:
            raise EvaluationContractError(
                "longitudinal point fields do not match schema"
            )
        metrics = value.get("metrics")
        failures = value.get("projection_failures")
        passed = value.get("projection_passed")
        if not isinstance(metrics, Mapping):
            raise EvaluationContractError(
                "longitudinal point metrics must be an object"
            )
        if not isinstance(failures, list) or any(
            not isinstance(item, str) for item in failures
        ):
            raise EvaluationContractError(
                "projection_failures must be a string array"
            )
        if not isinstance(passed, bool):
            raise EvaluationContractError(
                "projection_passed must be boolean"
            )

        normalized_metrics: dict[str, float] = {}
        for name, raw in metrics.items():
            if (
                not isinstance(name, str)
                or isinstance(raw, bool)
                or not isinstance(raw, int | float)
            ):
                raise EvaluationContractError(
                    "invalid persisted longitudinal metric"
                )
            normalized_metrics[name] = float(raw)

        return cls(
            release_id=str(value.get("release_id", "")),
            comparison_context_identity=_address(
                value.get("comparison_context_identity"),
                field_name="comparison_context_identity",
            ),
            input_identity=_address(
                value.get("input_identity"),
                field_name="input_identity",
            ),
            corpus_identity=_address(
                value.get("corpus_identity"),
                field_name="corpus_identity",
            ),
            policy_identity=_address(
                value.get("policy_identity"),
                field_name="policy_identity",
            ),
            evaluator_identity=_address(
                value.get("evaluator_identity"),
                field_name="evaluator_identity",
            ),
            candidate_runtime_identity=_address(
                value.get("candidate_runtime_identity"),
                field_name="candidate_runtime_identity",
            ),
            projection_identity=_address(
                value.get("projection_identity"),
                field_name="projection_identity",
            ),
            metrics=normalized_metrics,
            projection_passed=passed,
            projection_failures=tuple(failures),
            point_identity=_address(
                value.get("point_identity"),
                field_name="point_identity",
            ),
            schema=str(value.get("schema", "")),
        )

    @staticmethod
    def _body(
        *,
        release_id: str,
        comparison_context_identity: ContentAddress,
        input_identity: ContentAddress,
        corpus_identity: ContentAddress,
        policy_identity: ContentAddress,
        evaluator_identity: ContentAddress,
        candidate_runtime_identity: ContentAddress,
        projection_identity: ContentAddress,
        metrics: Mapping[str, float],
        projection_passed: bool,
        projection_failures: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "schema": KQM_LONGITUDINAL_POINT_SCHEMA_V1,
            "release_id": release_id,
            "comparison_context_identity": (
                comparison_context_identity.canonical_dict()
            ),
            "input_identity": input_identity.canonical_dict(),
            "corpus_identity": corpus_identity.canonical_dict(),
            "policy_identity": policy_identity.canonical_dict(),
            "evaluator_identity": evaluator_identity.canonical_dict(),
            "candidate_runtime_identity": (
                candidate_runtime_identity.canonical_dict()
            ),
            "projection_identity": projection_identity.canonical_dict(),
            "metrics": dict(sorted(metrics.items())),
            "projection_passed": projection_passed,
            "projection_failures": list(projection_failures),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            release_id=self.release_id,
            comparison_context_identity=self.comparison_context_identity,
            input_identity=self.input_identity,
            corpus_identity=self.corpus_identity,
            policy_identity=self.policy_identity,
            evaluator_identity=self.evaluator_identity,
            candidate_runtime_identity=self.candidate_runtime_identity,
            projection_identity=self.projection_identity,
            metrics=self.metrics,
            projection_passed=self.projection_passed,
            projection_failures=self.projection_failures,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "point_identity": self.point_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.comparison_context_identity != self.input_identity:
            raise EvaluationContractError(
                "comparison context must equal exact evaluation input identity"
            )
        expected = ContentAddress.for_value(self.canonical_body())
        if self.point_identity != expected:
            raise EvaluationContractError(
                "longitudinal point identity content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class KQMLongitudinalComparison:
    baseline_release: str
    current_release: str
    comparison_context_identity: ContentAddress
    policy_identity: ContentAddress
    baseline_point_identity: ContentAddress
    current_point_identity: ContentAddress
    deltas: tuple[KQMMetricDelta, ...]
    regression_free: bool
    comparison_identity: ContentAddress
    schema: str = KQM_LONGITUDINAL_COMPARISON_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != KQM_LONGITUDINAL_COMPARISON_SCHEMA_V1:
            raise EvaluationContractError(
                "unsupported longitudinal comparison schema: "
                f"{self.schema}"
            )
        object.__setattr__(
            self,
            "baseline_release",
            _identifier(
                self.baseline_release,
                field_name="baseline_release",
            ),
        )
        object.__setattr__(
            self,
            "current_release",
            _identifier(
                self.current_release,
                field_name="current_release",
            ),
        )
        if self.baseline_release == self.current_release:
            raise EvaluationContractError(
                "comparison requires two distinct releases"
            )
        names = tuple(delta.metric for delta in self.deltas)
        if not names or tuple(sorted(names)) != names:
            raise EvaluationContractError(
                "comparison deltas must be nonempty and sorted"
            )
        if len(set(names)) != len(names):
            raise EvaluationContractError(
                "comparison deltas must be unique"
            )
        expected_regression_free = all(
            delta.direction
            not in {
                KQMDeltaDirection.REGRESSED,
                KQMDeltaDirection.MISSING,
            }
            for delta in self.deltas
        )
        if self.regression_free != expected_regression_free:
            raise EvaluationContractError(
                "regression_free must match delta directions"
            )
        self.verify()

    @staticmethod
    def _body(
        *,
        baseline_release: str,
        current_release: str,
        comparison_context_identity: ContentAddress,
        policy_identity: ContentAddress,
        baseline_point_identity: ContentAddress,
        current_point_identity: ContentAddress,
        deltas: tuple[KQMMetricDelta, ...],
        regression_free: bool,
    ) -> dict[str, object]:
        return {
            "schema": KQM_LONGITUDINAL_COMPARISON_SCHEMA_V1,
            "baseline_release": baseline_release,
            "current_release": current_release,
            "comparison_context_identity": (
                comparison_context_identity.canonical_dict()
            ),
            "policy_identity": policy_identity.canonical_dict(),
            "baseline_point_identity": (
                baseline_point_identity.canonical_dict()
            ),
            "current_point_identity": (
                current_point_identity.canonical_dict()
            ),
            "deltas": [delta.canonical_dict() for delta in deltas],
            "regression_free": regression_free,
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            baseline_release=self.baseline_release,
            current_release=self.current_release,
            comparison_context_identity=self.comparison_context_identity,
            policy_identity=self.policy_identity,
            baseline_point_identity=self.baseline_point_identity,
            current_point_identity=self.current_point_identity,
            deltas=self.deltas,
            regression_free=self.regression_free,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "comparison_identity": (
                self.comparison_identity.canonical_dict()
            ),
        }

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.comparison_identity != expected:
            raise EvaluationContractError(
                "longitudinal comparison identity mismatch"
            )


def compare_kqm_points(
    baseline: KQMLongitudinalPoint,
    current: KQMLongitudinalPoint,
    *,
    policy: KQMPolicy,
) -> KQMLongitudinalComparison:
    if baseline.release_id == current.release_id:
        raise EvaluationContractError(
            "comparison requires two distinct releases"
        )
    if (
        baseline.comparison_context_identity
        != current.comparison_context_identity
    ):
        raise EvaluationContractError(
            "KQM points are not comparable: evaluation input identity changed"
        )
    if baseline.policy_identity != current.policy_identity:
        raise EvaluationContractError(
            "KQM points are not comparable: policy identity changed"
        )
    if baseline.policy_identity != policy.policy_identity:
        raise EvaluationContractError(
            "KQM comparison policy identity mismatch"
        )
    if baseline.evaluator_identity != current.evaluator_identity:
        raise EvaluationContractError(
            "KQM points are not comparable: evaluator identity changed"
        )
    if baseline.corpus_identity != current.corpus_identity:
        raise EvaluationContractError(
            "KQM points are not comparable: corpus identity changed"
        )

    expected_metrics = set(policy.metrics)
    unexpected = sorted(
        (set(baseline.metrics) | set(current.metrics)) - expected_metrics
    )
    if unexpected:
        raise EvaluationContractError(
            "unexpected longitudinal metrics: " + ", ".join(unexpected)
        )

    deltas: list[KQMMetricDelta] = []
    for metric in sorted(policy.metrics):
        left = baseline.metrics.get(metric)
        right = current.metrics.get(metric)
        if left is None or right is None:
            deltas.append(
                KQMMetricDelta(
                    metric=metric,
                    baseline=left,
                    current=right,
                    delta=None,
                    direction=KQMDeltaDirection.MISSING,
                )
            )
            continue

        delta = right - left
        if delta == 0:
            direction = KQMDeltaDirection.STABLE
        else:
            spec = policy.metrics[metric]
            improved = (
                delta > 0
                if spec.direction is MetricDirection.MIN
                else delta < 0
            )
            direction = (
                KQMDeltaDirection.IMPROVED
                if improved
                else KQMDeltaDirection.REGRESSED
            )
        deltas.append(
            KQMMetricDelta(
                metric=metric,
                baseline=left,
                current=right,
                delta=delta,
                direction=direction,
            )
        )

    ordered = tuple(deltas)
    regression_free = all(
        item.direction
        not in {
            KQMDeltaDirection.REGRESSED,
            KQMDeltaDirection.MISSING,
        }
        for item in ordered
    )
    body = KQMLongitudinalComparison._body(
        baseline_release=baseline.release_id,
        current_release=current.release_id,
        comparison_context_identity=baseline.comparison_context_identity,
        policy_identity=policy.policy_identity,
        baseline_point_identity=baseline.point_identity,
        current_point_identity=current.point_identity,
        deltas=ordered,
        regression_free=regression_free,
    )
    return KQMLongitudinalComparison(
        baseline_release=baseline.release_id,
        current_release=current.release_id,
        comparison_context_identity=baseline.comparison_context_identity,
        policy_identity=policy.policy_identity,
        baseline_point_identity=baseline.point_identity,
        current_point_identity=current.point_identity,
        deltas=ordered,
        regression_free=regression_free,
        comparison_identity=ContentAddress.for_value(body),
    )


class PersistentKQMHistory:
    """Tamper-evident KQM-03 history for one exact evaluation context.

    The store is a measurement ledger, not Product truth or release authority.
    """

    _CASE_ID = "@kqm-longitudinal-v1"
    _EVENT_TYPE = "KQM_LONGITUDINAL_POINT_V1"

    def __init__(
        self,
        path: str | Path,
        *,
        storage_runtime_identity: RuntimeIdentity,
        comparison_context_identity: ContentAddress,
        policy_identity: ContentAddress,
    ) -> None:
        self._ledger = AppendOnlyReplayLedger(path)
        self._storage_runtime_identity = storage_runtime_identity
        self._comparison_context_identity = comparison_context_identity
        self._policy_identity = policy_identity

    def append(self, point: KQMLongitudinalPoint) -> None:
        if (
            point.comparison_context_identity
            != self._comparison_context_identity
        ):
            raise EvaluationContractError(
                "history point evaluation context mismatch"
            )
        if point.policy_identity != self._policy_identity:
            raise EvaluationContractError(
                "history point policy identity mismatch"
            )
        if any(
            existing.release_id == point.release_id
            for existing in self.points()
        ):
            raise EvaluationContractError(
                f"duplicate longitudinal release_id: {point.release_id}"
            )
        self._ledger.append(
            case_id=self._CASE_ID,
            event_type=self._EVENT_TYPE,
            runtime_identity=self._storage_runtime_identity,
            payload=point.canonical_dict(),
        )

    def points(self) -> tuple[KQMLongitudinalPoint, ...]:
        result: list[KQMLongitudinalPoint] = []
        for record in self._ledger.verify():
            if (
                record.case_id != self._CASE_ID
                or record.event_type != self._EVENT_TYPE
            ):
                raise EvaluationContractError(
                    "KQM history contains foreign provenance event"
                )
            point = KQMLongitudinalPoint.from_dict(record.payload)
            if (
                point.comparison_context_identity
                != self._comparison_context_identity
            ):
                raise EvaluationContractError(
                    "persisted KQM evaluation context mismatch"
                )
            if point.policy_identity != self._policy_identity:
                raise EvaluationContractError(
                    "persisted KQM policy identity mismatch"
                )
            result.append(point)

        releases = tuple(point.release_id for point in result)
        if len(set(releases)) != len(releases):
            raise EvaluationContractError(
                "persisted KQM history contains duplicate releases"
            )
        return tuple(result)

    def compare(
        self,
        baseline_release: str,
        current_release: str,
        *,
        policy: KQMPolicy,
    ) -> KQMLongitudinalComparison:
        if policy.policy_identity != self._policy_identity:
            raise EvaluationContractError(
                "history comparison policy identity mismatch"
            )
        by_release = {
            point.release_id: point for point in self.points()
        }
        try:
            baseline = by_release[baseline_release]
            current = by_release[current_release]
        except KeyError as exc:
            raise EvaluationContractError(
                "history comparison references unknown release"
            ) from exc
        return compare_kqm_points(
            baseline,
            current,
            policy=policy,
        )

    def head_digest(self) -> str:
        return self._ledger.head_digest()
