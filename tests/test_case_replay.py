from dataclasses import replace

from knowledge.case_replay import (
    CaseReplayRecord,
    ReplayAgentBinding,
    compare_replay,
)
from knowledge.models.case_snapshot import CaseSnapshot

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def record() -> CaseReplayRecord:
    snapshot = CaseSnapshot(
        snapshot_id="snap-1",
        case_key="CASE-1",
        git_commit="deadbeef",
    )
    return CaseReplayRecord.from_snapshot(
        snapshot,
        manifest_sha256=A,
        source_sha256=(("doc-b", C), ("doc-a", B)),
        pipeline_version="pipeline-1.0.0",
        graph_sha256=D,
        agent_bindings=(
            ReplayAgentBinding(
                agent_id="agent-b",
                agent_version="1.0.0",
                contract_sha256=C,
            ),
            ReplayAgentBinding(
                agent_id="agent-a",
                agent_version="1.0.0",
                contract_sha256=B,
            ),
        ),
        renderer_version="renderer-1.0.0",
    )


def test_replay_fingerprint_is_deterministic_and_order_independent() -> None:
    first = record()
    reordered = CaseReplayRecord(
        case_key=first.case_key,
        snapshot_id=first.snapshot_id,
        manifest_sha256=first.manifest_sha256,
        source_sha256=tuple(reversed(first.source_sha256)),
        pipeline_version=first.pipeline_version,
        graph_sha256=first.graph_sha256,
        agent_bindings=tuple(reversed(first.agent_bindings)),
        renderer_version=first.renderer_version,
        git_commit=first.git_commit,
    )

    assert first.fingerprint() == reordered.fingerprint()
    assert compare_replay(first, reordered).matches is True


def test_replay_detects_graph_drift_without_overwriting_expected_state() -> None:
    expected = record()
    observed = replace(expected, graph_sha256=A)

    comparison = compare_replay(expected, observed)

    assert comparison.matches is False
    assert comparison.drift_fields == ("graph_sha256",)
    assert comparison.expected_fingerprint == expected.fingerprint()
    assert comparison.observed_fingerprint == observed.fingerprint()


def test_replay_detects_agent_contract_drift() -> None:
    expected = record()
    changed_binding = replace(expected.agent_bindings[0], contract_sha256=D)
    observed = replace(
        expected,
        agent_bindings=(changed_binding, expected.agent_bindings[1]),
    )

    comparison = compare_replay(expected, observed)

    assert comparison.matches is False
    assert comparison.drift_fields == ("agent_bindings",)


def test_replay_rejects_invalid_hashes() -> None:
    try:
        replace(record(), graph_sha256="not-a-sha")
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("invalid graph hash must be rejected")
