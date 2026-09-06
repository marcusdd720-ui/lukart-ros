from __future__ import annotations

from pathlib import Path

import pytest

from core.p2 import AgentProvider, AgentTask, PluginRegistry
from core.p3 import (
    CapabilityPolicy,
    HardenedAgentRuntime,
    MetricObjective,
    P3ContractError,
    PersistentLongitudinalQualityStore,
    ProviderHealth,
    QualityDirection,
    QualityPoint,
    RuntimeIdentity,
    ScaleProfile,
    measure_scale_profile,
)


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="3.0.0",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("boundary@3.0.0",),
    )


def test_runtime_identity_rejects_non_digest_material() -> None:
    with pytest.raises(P3ContractError, match="code_sha"):
        RuntimeIdentity(
            code_sha="not-a-git-sha",
            schema_version="3.0.0",
            config_digest="b" * 64,
            corpus_digest="c" * 64,
        )
    with pytest.raises(P3ContractError, match="config_digest"):
        RuntimeIdentity(
            code_sha="a" * 40,
            schema_version="3.0.0",
            config_digest="g" * 64,
            corpus_digest="c" * 64,
        )


def test_persistent_quality_store_survives_reopen_and_detects_tamper(
    tmp_path: Path,
) -> None:
    path = tmp_path / "quality.jsonl"
    objectives = {
        "coverage": MetricObjective.HIGHER_IS_BETTER,
        "unsupported": MetricObjective.LOWER_IS_BETTER,
    }
    store = PersistentLongitudinalQualityStore(
        path,
        runtime_identity=_identity(),
        objectives=objectives,
    )
    store.append(
        QualityPoint(
            release_id="r1",
            code_sha="1" * 40,
            corpus_digest="d" * 64,
            metrics={"coverage": 0.90, "unsupported": 0.10},
        )
    )
    store.append(
        QualityPoint(
            release_id="r2",
            code_sha="2" * 40,
            corpus_digest="d" * 64,
            metrics={"coverage": 0.95, "unsupported": 0.05},
        )
    )

    reopened = PersistentLongitudinalQualityStore(
        path,
        runtime_identity=_identity(),
        objectives=objectives,
    )
    assert tuple(point.release_id for point in reopened.points()) == ("r1", "r2")
    deltas = {delta.metric: delta for delta in reopened.compare("r1", "r2")}
    assert deltas["coverage"].direction is QualityDirection.IMPROVED
    assert deltas["unsupported"].direction is QualityDirection.IMPROVED
    assert len(reopened.digest()) == 64

    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"coverage":0.9', '"coverage":0.8'), encoding="utf-8")
    with pytest.raises(P3ContractError, match="digest"):
        reopened.points()


class AlwaysBrokenAgent(AgentProvider):
    plugin_id = "always-broken"
    version = "3.0.0"
    capabilities = frozenset({"boundary-analysis"})

    @classmethod
    def execute(cls, task: AgentTask):
        raise RuntimeError("synthetic hard failure")


def test_agent_runtime_circuit_breaker_quarantines_repeated_failure() -> None:
    registry: PluginRegistry[AgentProvider] = PluginRegistry()
    registry.register(AlwaysBrokenAgent)
    runtime = HardenedAgentRuntime(
        registry,
        {
            "boundary-analysis": CapabilityPolicy(
                capability="boundary-analysis",
                timeout_seconds=0.1,
                total_timeout_seconds=0.2,
                max_concurrency=1,
                failure_threshold=1,
                certified_provider_identities=(AlwaysBrokenAgent.identity(),),
            )
        },
    )

    with pytest.raises(P3ContractError, match="all certified providers failed"):
        runtime.run(AgentTask("B-1", "boundary-analysis", {}))
    assert runtime.health(AlwaysBrokenAgent.identity()) is ProviderHealth.UNHEALTHY
    assert runtime.failure_count(AlwaysBrokenAgent.identity()) == 1

    with pytest.raises(P3ContractError, match="no healthy certified provider"):
        runtime.run(AgentTask("B-2", "boundary-analysis", {}))


def test_scale_profile_executes_full_semantic_blast_radius() -> None:
    profile = ScaleProfile(
        "blast",
        evidence_count=64,
        graph_nodes=256,
        replay_count=16,
        concurrency=4,
    )
    measurement = measure_scale_profile(profile)
    assert measurement.blast_radius_size == 257
    assert measurement.cache_hit_ratio > 0
