from __future__ import annotations

from dataclasses import replace

from knowledge.case_replay import CaseReplayRecord, ReplayAgentBinding
from validation.replay_regression import ReplayRegressionPolicy, evaluate_replay_regression

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def _record() -> CaseReplayRecord:
    return CaseReplayRecord(
        case_key="SYN-REPLAY-1",
        snapshot_id="snapshot-1",
        manifest_sha256=A,
        source_sha256=(("doc-1", B),),
        pipeline_version="pipeline-1.0.0",
        graph_sha256=C,
        agent_bindings=(ReplayAgentBinding("agent-1", "1.0.0", D),),
        renderer_version="renderer-1.0.0",
        git_commit="a" * 40,
    )


def test_replay_regression_passes_with_no_drift_when_none_expected() -> None:
    baseline = _record()
    result = evaluate_replay_regression(baseline, baseline, ReplayRegressionPolicy())

    assert result.passed is True
    assert result.comparison.matches is True
    assert result.unexpected_drift_fields == ()
    assert result.missing_expected_drift_fields == ()


def test_replay_regression_accepts_exact_declared_drift() -> None:
    baseline = _record()
    candidate = replace(baseline, renderer_version="renderer-2.0.0")
    policy = ReplayRegressionPolicy(expected_drift_fields=("renderer_version",))

    result = evaluate_replay_regression(baseline, candidate, policy)

    assert result.passed is True
    assert result.comparison.drift_fields == ("renderer_version",)


def test_replay_regression_rejects_unexpected_drift() -> None:
    baseline = _record()
    candidate = replace(
        baseline,
        renderer_version="renderer-2.0.0",
        graph_sha256=D,
    )
    policy = ReplayRegressionPolicy(expected_drift_fields=("renderer_version",))

    result = evaluate_replay_regression(baseline, candidate, policy)

    assert result.passed is False
    assert result.unexpected_drift_fields == ("graph_sha256",)


def test_replay_regression_rejects_declared_drift_that_did_not_happen() -> None:
    baseline = _record()
    policy = ReplayRegressionPolicy(expected_drift_fields=("renderer_version",))

    result = evaluate_replay_regression(baseline, baseline, policy)

    assert result.passed is False
    assert result.missing_expected_drift_fields == ("renderer_version",)
