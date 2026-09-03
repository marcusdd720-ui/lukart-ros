"""Deterministic regression policy for Case Replay comparisons."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.case_replay import CaseReplayComparison, CaseReplayRecord, compare_replay


@dataclass(frozen=True, slots=True)
class ReplayRegressionPolicy:
    """Explicitly declare which replay fields may drift for a candidate change."""

    expected_drift_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(sorted(field.strip() for field in self.expected_drift_fields))
        if not all(normalized):
            raise ValueError("expected replay drift fields cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("expected replay drift fields must be unique")
        object.__setattr__(self, "expected_drift_fields", normalized)


@dataclass(frozen=True, slots=True)
class ReplayRegressionResult:
    passed: bool
    comparison: CaseReplayComparison
    expected_drift_fields: tuple[str, ...]
    unexpected_drift_fields: tuple[str, ...]
    missing_expected_drift_fields: tuple[str, ...]


def evaluate_replay_regression(
    baseline: CaseReplayRecord,
    candidate: CaseReplayRecord,
    policy: ReplayRegressionPolicy,
) -> ReplayRegressionResult:
    """Pass only when observed replay drift exactly matches the declared policy."""

    comparison = compare_replay(baseline, candidate)
    observed = set(comparison.drift_fields)
    expected = set(policy.expected_drift_fields)
    unexpected = tuple(sorted(observed - expected))
    missing = tuple(sorted(expected - observed))
    return ReplayRegressionResult(
        passed=not unexpected and not missing,
        comparison=comparison,
        expected_drift_fields=policy.expected_drift_fields,
        unexpected_drift_fields=unexpected,
        missing_expected_drift_fields=missing,
    )
