from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from core.p2 import AgentProvider, AgentResult, AgentTask, ExecutionBudget, PluginRegistry
from core.p3 import (
    ApiContractRegistry,
    ApiResourceKind,
    AppendOnlyReplayLedger,
    CancellationToken,
    CapabilityPolicy,
    CaseMigrationRegistry,
    ControlledExperiment,
    ControlledExperimentManager,
    ExperimentState,
    HardenedAgentRuntime,
    IsolatedPluginRegistry,
    LongitudinalQualityStore,
    MetricObjective,
    MigrationStep,
    P3ContractError,
    PluginManifest,
    PluginSdkBoundary,
    ProviderHealth,
    QualityDirection,
    QualityPoint,
    RuntimeIdentity,
    ScaleBudget,
    ScaleProfile,
    SemanticChangeGraph,
    StableApiResource,
    TrustLevel,
    VersionedCase,
    build_explainability_dossier,
    certify_scale,
    content_digest,
    measure_scale_profile,
    repeated_measurement_digest,
)
from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="3.0.0",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("synthetic@3.0.0",),
    )


def _reasoning_result():
    fact = ReasoningArtifact(
        artifact_id="F-1",
        statement="Synthetic fact.",
        status=KnowledgeStatus.FACT,
        evidence_refs=("EV-1",),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C-1",
        statement="Synthetic conclusion.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("F-1",),
    )
    return ReasoningEngine((fact, conclusion)).evaluate("C-1")


def test_hardening_canonical_digest_is_order_independent_for_mappings() -> None:
    left = {"b": 2, "a": {"z": 1, "x": 0}}
    right = {"a": {"x": 0, "z": 1}, "b": 2}
    assert content_digest(left) == content_digest(right)


def test_p3_01_reasoning_change_graph_produces_reason_paths() -> None:
    graph = SemanticChangeGraph.from_reasoning(_reasoning_result())
    graph.validate_acyclic()
    plan = graph.plan(("EV-1",))
    assert plan.affected_ids == ("@decision", "C-1", "EV-1", "F-1")
    decision_path = next(
        item
        for item in plan.paths
        if item.changed_id == "EV-1" and item.affected_id == "@decision"
    )
    assert decision_path.path == ("EV-1", "F-1", "C-1", "@decision")
    assert len(plan.graph_digest) == 64


def test_p3_01_change_graph_rejects_unknown_and_cycles() -> None:
    graph = SemanticChangeGraph({"A": ("B",), "B": ("A",)})
    with pytest.raises(P3ContractError, match="cycle"):
        graph.validate_acyclic()
    with pytest.raises(P3ContractError, match="unknown"):
        SemanticChangeGraph({"A": ()}).plan(("MISSING",))


def test_p3_02_ledger_is_persistent_append_only_and_tamper_evident(tmp_path: Path) -> None:
    path = tmp_path / "provenance.jsonl"
    ledger = AppendOnlyReplayLedger(path)
    first = ledger.append(
        case_id="SYN-1",
        event_type="REASONING",
        runtime_identity=_identity(),
        payload={"reasoning_digest": "d" * 64},
    )
    second = ledger.append(
        case_id="SYN-1",
        event_type="RENDER",
        runtime_identity=_identity(),
        payload={"renderer_digest": "e" * 64},
    )
    assert second.sequence == 1
    assert second.previous_record_digest == first.record_digest
    assert AppendOnlyReplayLedger(path).head_digest() == second.record_digest

    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace("RENDER", "RENDER-TAMPER"), encoding="utf-8")
    with pytest.raises(P3ContractError, match="digest"):
        ledger.verify()


def test_p3_02_ledger_detects_partial_write(tmp_path: Path) -> None:
    path = tmp_path / "partial.jsonl"
    path.write_text('{"incomplete":true}', encoding="utf-8")
    with pytest.raises(P3ContractError, match="partial"):
        AppendOnlyReplayLedger(path).verify()


def test_p3_03_migrations_are_explicit_deterministic_and_source_preserving() -> None:
    registry = CaseMigrationRegistry()
    registry.register(
        MigrationStep("v1", "v2", lambda payload: {**payload, "schema_marker": "v2"})
    )
    registry.register(
        MigrationStep("v2", "v3", lambda payload: {**payload, "normalized": True})
    )
    source = VersionedCase.build(case_id="SYN-1", schema_version="v1", payload={"x": 1})
    report = registry.migrate(source, "v3")
    assert report.path == ("v1", "v2", "v3")
    assert report.target.schema_version == "v3"
    assert report.target.payload["normalized"] is True
    assert source.payload == {"x": 1}
    assert registry.migrate(report.target, "v3").target == report.target


def test_p3_03_non_deterministic_migration_fails_closed() -> None:
    calls = {"value": 0}

    def unstable(payload):
        calls["value"] += 1
        return {**payload, "counter": calls["value"]}

    registry = CaseMigrationRegistry()
    registry.register(MigrationStep("v1", "v2", unstable))
    source = VersionedCase.build(case_id="SYN-1", schema_version="v1", payload={"x": 1})
    with pytest.raises(P3ContractError, match="non-deterministic"):
        registry.migrate(source, "v2")


def test_p3_04_dossier_is_bound_to_reasoning_and_exposes_lineage() -> None:
    result = _reasoning_result()
    dossier = build_explainability_dossier(result, contradictions=("SYN-CONFLICT",))
    assert dossier.source_reasoning_digest == result.digest()
    assert dossier.support_lineage == ("C-1", "F-1")
    assert dossier.evidence_refs == ("EV-1",)
    assert dossier.contradictions == ("SYN-CONFLICT",)
    assert dossier.counterfactual_checks
    assert len(dossier.digest()) == 64


def test_p3_05_quality_objectives_are_unambiguous_and_missing_is_visible() -> None:
    store = LongitudinalQualityStore(
        {
            "evidence_coverage": MetricObjective.HIGHER_IS_BETTER,
            "unsupported_conclusion_rate": MetricObjective.LOWER_IS_BETTER,
            "missing_metric": MetricObjective.HIGHER_IS_BETTER,
        }
    )
    store.append(
        QualityPoint(
            "r1",
            "a" * 40,
            "b" * 64,
            {"evidence_coverage": 0.9, "unsupported_conclusion_rate": 0.1},
        )
    )
    store.append(
        QualityPoint(
            "r2",
            "c" * 40,
            "b" * 64,
            {"evidence_coverage": 0.95, "unsupported_conclusion_rate": 0.05},
        )
    )
    result = {item.metric: item for item in store.compare("r1", "r2")}
    assert result["evidence_coverage"].direction is QualityDirection.IMPROVED
    assert result["unsupported_conclusion_rate"].direction is QualityDirection.IMPROVED
    assert result["missing_metric"].direction is QualityDirection.MISSING


def test_p3_06_controlled_experiment_cannot_skip_validation_or_approver() -> None:
    manager = ControlledExperimentManager()
    experiment = ControlledExperiment("EXP-1", ExperimentState.FAILURE, "a" * 64)
    candidate = manager.transition(experiment, ExperimentState.CANDIDATE)
    running = manager.transition(candidate, ExperimentState.EXPERIMENT)
    validation = manager.transition(running, ExperimentState.VALIDATION)
    with pytest.raises(P3ContractError, match="validation digest"):
        manager.transition(validation, ExperimentState.PROMOTION)
    promoted = manager.transition(
        validation,
        ExperimentState.PROMOTION,
        validation_digest="b" * 64,
        approver_id="reviewer-1",
    )
    assert promoted.trust_level is TrustLevel.VALIDATED
    monitored = manager.transition(promoted, ExperimentState.MONITORING)
    assert monitored.trust_level is TrustLevel.TRUSTED
    rolled_back = manager.transition(monitored, ExperimentState.ROLLED_BACK)
    assert rolled_back.trust_level is TrustLevel.CANDIDATE
    with pytest.raises(P3ContractError, match="illegal"):
        manager.transition(candidate, ExperimentState.PROMOTION)


class HealthyAgent(AgentProvider):
    plugin_id = "healthy"
    version = "3.0.0"
    capabilities = frozenset({"analysis"})

    @classmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        return AgentResult(task.task_id, cls.plugin_id, cls.version, 1, {"candidate": True})


class BrokenAgent(AgentProvider):
    plugin_id = "aaa-broken"
    version = "3.0.0"
    capabilities = frozenset({"analysis"})

    @classmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        raise RuntimeError("synthetic provider failure")


class SlowAgent(AgentProvider):
    plugin_id = "slow"
    version = "3.0.0"
    capabilities = frozenset({"slow-analysis"})

    @classmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        time.sleep(0.05)
        return AgentResult(task.task_id, cls.plugin_id, cls.version, 1, {})


def _runtime_registry() -> PluginRegistry[AgentProvider]:
    registry: PluginRegistry[AgentProvider] = PluginRegistry()
    registry.register(HealthyAgent)
    registry.register(BrokenAgent)
    registry.register(SlowAgent)
    return registry


def test_p3_07_runtime_uses_certified_fallback_and_audits() -> None:
    runtime = HardenedAgentRuntime(
        _runtime_registry(),
        {
            "analysis": CapabilityPolicy(
                "analysis",
                timeout_seconds=0.5,
                max_concurrency=1,
                certified_provider_identities=(BrokenAgent.identity(), HealthyAgent.identity()),
            )
        },
    )
    execution = runtime.run(AgentTask("T-1", "analysis", {"x": 1}, ExecutionBudget(4)))
    assert execution.result.provider_id == "healthy"
    assert execution.audit.output_digest is not None
    records = runtime.audit_records()
    assert len(records) == 2
    assert records[-1].outcome.value == "SUCCESS"


def test_p3_07_runtime_timeout_cancellation_and_health_fail_closed() -> None:
    runtime = HardenedAgentRuntime(
        _runtime_registry(),
        {
            "slow-analysis": CapabilityPolicy(
                "slow-analysis",
                timeout_seconds=0.005,
                max_concurrency=1,
                certified_provider_identities=(SlowAgent.identity(),),
            )
        },
    )
    with pytest.raises(P3ContractError, match="all certified providers failed"):
        runtime.run(AgentTask("T-SLOW", "slow-analysis", {}))
    runtime.set_health(SlowAgent.identity(), ProviderHealth.UNHEALTHY)
    with pytest.raises(P3ContractError, match="no healthy certified provider"):
        runtime.run(AgentTask("T-DOWN", "slow-analysis", {}))

    token = CancellationToken()
    token.cancel()
    with pytest.raises(P3ContractError, match="cancelled"):
        runtime.run(AgentTask("T-CANCEL", "slow-analysis", {}), cancellation=token)
    assert runtime.isolation_level == "logical-thread-boundary"


def test_p3_08_api_contract_is_allowlisted_double_digest_bound_and_fail_closed() -> None:
    resource = StableApiResource(
        kind=ApiResourceKind.CASE,
        resource_id="SYN-1",
        payload={"synthetic": True},
        runtime_identity=_identity(),
    )
    raw = resource.to_envelope().to_json()
    registry = ApiContractRegistry()
    registry.register_v1_defaults()
    assert registry.decode(raw).schema == "lukart.api.case.v1"

    tampered = json.loads(raw)
    tampered["payload"]["payload"]["synthetic"] = False
    # Re-signing only the outer P2 envelope is insufficient because P3 inner digest is bound.
    tampered["payload_digest"] = content_digest(tampered["payload"])
    with pytest.raises(P3ContractError, match="inner payload digest"):
        registry.decode(json.dumps(tampered))

    empty_registry = ApiContractRegistry()
    with pytest.raises(P3ContractError, match="unsupported API contract"):
        empty_registry.decode(raw)


def test_p3_08_trusted_analytical_api_state_requires_authorization_marker() -> None:
    with pytest.raises(P3ContractError, match="authorization marker"):
        StableApiResource(
            kind=ApiResourceKind.FACT,
            resource_id="F-1",
            payload={"statement": "synthetic"},
            runtime_identity=_identity(),
            trust_level=TrustLevel.TRUSTED,
        )


def test_p3_09_scale_measurement_is_deterministic_in_semantic_work() -> None:
    profile = ScaleProfile(
        "ci-small",
        evidence_count=32,
        graph_nodes=64,
        replay_count=8,
        concurrency=2,
    )
    measurement = measure_scale_profile(profile)
    assert measurement.duration_seconds >= 0
    assert measurement.peak_memory_bytes > 0
    assert measurement.cache_hit_ratio > 0
    digests = repeated_measurement_digest(lambda: measure_scale_profile(profile), repetitions=2)
    assert len(set(digests)) == 1
    certification = certify_scale(
        measurement,
        ScaleBudget(
            max_duration_seconds=30.0,
            max_peak_memory_bytes=128 * 1024 * 1024,
            min_cache_hit_ratio=0.1,
        ),
    )
    assert certification.passed is True


def test_p3_10_plugin_sdk_rejects_permissions_dependencies_and_manifest_spoofing() -> None:
    boundary = PluginSdkBoundary(
        host_api_version="1.0.0",
        allowed_permissions=("read:synthetic-case",),
        allowed_dependencies=("stdlib",),
    )
    registry = IsolatedPluginRegistry(boundary)
    manifest = PluginManifest(
        plugin_id=HealthyAgent.plugin_id,
        version=HealthyAgent.version,
        capabilities=("analysis",),
        api_version="1.0.0",
        permissions=("read:synthetic-case",),
        dependencies=("stdlib",),
    )
    registry.register(HealthyAgent, manifest)
    assert registry.providers() == (HealthyAgent,)
    assert registry.by_capability("analysis") == (HealthyAgent,)
    assert len(registry.registry_digest()) == 64
    assert boundary.isolation_level == "logical-manifest-boundary"

    denied = PluginManifest(
        plugin_id=BrokenAgent.plugin_id,
        version=BrokenAgent.version,
        capabilities=("analysis",),
        api_version="1.0.0",
        permissions=("write:trusted-core",),
    )
    with pytest.raises(P3ContractError, match="permissions_denied"):
        IsolatedPluginRegistry(boundary).register(BrokenAgent, denied)

    spoofed = PluginManifest(
        plugin_id="other",
        version=HealthyAgent.version,
        capabilities=("analysis",),
        api_version="1.0.0",
    )
    with pytest.raises(P3ContractError, match="identity"):
        IsolatedPluginRegistry(boundary).register(HealthyAgent, spoofed)
