from dataclasses import replace

from knowledge.case_replay import CaseReplayRecord, ReplayAgentBinding
from knowledge.cognitive_replay import (
    CognitiveArtifactBinding,
    CognitiveReplayEnvelope,
    compare_cognitive_replay,
)
from knowledge.models.case_snapshot import CaseSnapshot

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64


def _case_replay() -> CaseReplayRecord:
    snapshot = CaseSnapshot(
        snapshot_id="snap-cognitive",
        case_key="CASE-E2E",
        git_commit="deadbeef",
    )
    return CaseReplayRecord.from_snapshot(
        snapshot,
        manifest_sha256=A,
        source_sha256=(("source-1", B),),
        pipeline_version="pipeline-1.0",
        graph_sha256=C,
        agent_bindings=(ReplayAgentBinding("reasoning", "1.0", D),),
        renderer_version="renderer-v1",
    )


def _artifacts() -> tuple[CognitiveArtifactBinding, ...]:
    return (
        CognitiveArtifactBinding("case_model", "CASE-E2E", 2, A),
        CognitiveArtifactBinding("problem", "PROBLEM-1", 3, B),
        CognitiveArtifactBinding("evidence", "ASSESS-1", 4, C),
        CognitiveArtifactBinding("decision", "DECISION-1", 5, D),
        CognitiveArtifactBinding("strategy", "STRATEGY-1", 6, E),
        CognitiveArtifactBinding("plan", "PLAN-1", 7, A),
        CognitiveArtifactBinding("document", "DOC-1", 1, B),
    )


def test_cognitive_replay_is_deterministic_and_order_independent() -> None:
    expected = CognitiveReplayEnvelope.from_case_replay(
        _case_replay(),
        artifacts=_artifacts(),
        chain_version="cognitive-chain-1.0",
    )
    reordered = CognitiveReplayEnvelope(
        case_replay_fingerprint=expected.case_replay_fingerprint,
        artifacts=tuple(reversed(expected.artifacts)),
        chain_version=expected.chain_version,
    )

    assert expected.fingerprint() == reordered.fingerprint()
    assert compare_cognitive_replay(expected, reordered).matches is True


def test_cognitive_replay_detects_artifact_version_drift() -> None:
    expected = CognitiveReplayEnvelope.from_case_replay(
        _case_replay(),
        artifacts=_artifacts(),
        chain_version="cognitive-chain-1.0",
    )
    changed = replace(expected.artifacts[3], version=6)
    observed = replace(
        expected,
        artifacts=(*expected.artifacts[:3], changed, *expected.artifacts[4:]),
    )

    comparison = compare_cognitive_replay(expected, observed)

    assert comparison.matches is False
    assert comparison.drift_fields == ("artifacts",)


def test_cognitive_replay_detects_underlying_case_replay_drift() -> None:
    expected_case = _case_replay()
    observed_case = replace(expected_case, graph_sha256=E)
    expected = CognitiveReplayEnvelope.from_case_replay(
        expected_case,
        artifacts=_artifacts(),
        chain_version="cognitive-chain-1.0",
    )
    observed = CognitiveReplayEnvelope.from_case_replay(
        observed_case,
        artifacts=_artifacts(),
        chain_version="cognitive-chain-1.0",
    )

    comparison = compare_cognitive_replay(expected, observed)

    assert comparison.matches is False
    assert comparison.drift_fields == ("case_replay_fingerprint",)


def test_invalid_cognitive_digest_is_rejected() -> None:
    try:
        CognitiveArtifactBinding("decision", "DEC-1", 1, "not-a-digest")
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("invalid cognitive artifact digest must be rejected")
