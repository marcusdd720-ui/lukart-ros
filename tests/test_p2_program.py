from __future__ import annotations

import json

import pytest

from core.p2 import (
    AgentProvider,
    AgentResult,
    AgentTask,
    ApiEnvelope,
    BoundedAgentRuntime,
    DependencyGraph,
    ExecutionBudget,
    FailureEvent,
    FailureSeverity,
    LruArtifactCache,
    MetricDirection,
    PluginRegistry,
    QualityObservation,
    QualityTrendAnalyzer,
    ReplaySnapshot,
    RuntimeContractError,
    SemanticSeverity,
    TrendStatus,
    bounded_parallel_map,
    compare_replays,
    discover_gold_candidates,
    explain_result,
    semantic_diff,
)
from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact


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


def test_p2_01_semantic_regression_detects_critical_meaning_change() -> None:
    before = {
        "decision": {"outcome": "ABSTAIN"},
        "status": "HYPOTHESIS",
        "presentation": {"title": "A"},
    }
    after = {
        "decision": {"outcome": "CONCLUDE"},
        "status": "FACT",
        "presentation": {"title": "B"},
    }
    result = semantic_diff(before, after)
    assert result.changed is True
    assert result.highest_severity is SemanticSeverity.CRITICAL
    assert {change.path for change in result.changes} == {
        "decision.outcome",
        "presentation.title",
        "status",
    }


def test_p2_02_blast_radius_is_transitive_and_deterministic() -> None:
    graph = DependencyGraph(
        {
            "F-1": (),
            "C-1": ("F-1",),
            "D-1": ("C-1",),
            "UNRELATED": (),
        }
    )
    assert graph.blast_radius(("F-1",)) == ("C-1", "D-1", "F-1")
    assert graph.blast_radius(("missing",)) == ()


def test_p2_03_cross_version_replay_exposes_semantic_divergence() -> None:
    left = ReplaySnapshot.build(
        version="1.1",
        code_sha="sha-a",
        input_payload={"case": "SYN-1"},
        output={"decision": {"outcome": "ABSTAIN"}, "status": "UNRESOLVED"},
    )
    right = ReplaySnapshot.build(
        version="2.0",
        code_sha="sha-b",
        input_payload={"case": "SYN-1"},
        output={"decision": {"outcome": "CONCLUDE"}, "status": "CONCLUSION"},
    )
    comparison = compare_replays(left, right)
    assert comparison.same_input is True
    assert comparison.byte_equivalent_output is False
    assert comparison.semantic.highest_severity is SemanticSeverity.CRITICAL
    assert comparison.requires_review is True


def test_p2_04_longitudinal_quality_marks_regression_and_improvement() -> None:
    analyzer = QualityTrendAnalyzer(
        {
            "evidence_coverage": MetricDirection.MIN,
            "unsupported_conclusion_rate": MetricDirection.MAX,
        }
    )
    baseline = QualityObservation(
        "1.1", {"evidence_coverage": 0.96, "unsupported_conclusion_rate": 0.02}
    )
    current = QualityObservation(
        "2.0", {"evidence_coverage": 0.99, "unsupported_conclusion_rate": 0.03}
    )
    trends = {trend.metric: trend for trend in analyzer.compare(baseline, current)}
    assert trends["evidence_coverage"].status is TrendStatus.IMPROVED
    assert trends["unsupported_conclusion_rate"].status is TrendStatus.REGRESSED


def test_p2_05_explainability_preserves_lineage_evidence_and_counterfactuals() -> None:
    explanation = explain_result(_reasoning_result())
    assert explanation.outcome == "CONCLUDE"
    assert explanation.conclusion_artifact_id == "C-1"
    assert explanation.support_lineage == ("C-1", "F-1")
    assert explanation.evidence_refs == ("EV-1",)
    assert explanation.decisive_factors
    assert any("F-1" in item for item in explanation.counterfactual_checks)


def test_p2_06_gold_discovery_proposes_only_synthetic_repeated_failures() -> None:
    events = (
        FailureEvent("SIG-A", FailureSeverity.HIGH, "SYN-1", True),
        FailureEvent("SIG-A", FailureSeverity.MEDIUM, "SYN-2", True),
        FailureEvent("SIG-A", FailureSeverity.CRITICAL, "PRIVATE-1", False),
        FailureEvent("SIG-B", FailureSeverity.CRITICAL, "SYN-3", True),
    )
    candidates = discover_gold_candidates(events)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.signature == "SIG-A"
    assert candidate.occurrences == 2
    assert candidate.max_severity is FailureSeverity.HIGH
    assert candidate.promotion_state == "CANDIDATE"


class SyntheticAgent(AgentProvider):
    plugin_id = "synthetic-agent"
    version = "2.0.0"
    capabilities = frozenset({"synthetic-analysis"})

    @classmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            provider_id=cls.plugin_id,
            provider_version=cls.version,
            steps_used=2,
            artifact={"status": "FACT", "evidence_refs": ["SYN-EV-1"]},
        )


class OverBudgetAgent(AgentProvider):
    plugin_id = "over-budget"
    version = "2.0.0"
    capabilities = frozenset({"over-budget"})

    @classmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            provider_id=cls.plugin_id,
            provider_version=cls.version,
            steps_used=task.budget.max_steps + 1,
            artifact={},
        )


def test_p2_07_agent_runtime_routes_by_capability_and_enforces_budget() -> None:
    registry: PluginRegistry[AgentProvider] = PluginRegistry()
    registry.register(SyntheticAgent)
    registry.register(OverBudgetAgent)
    runtime = BoundedAgentRuntime(registry)
    result = runtime.run(AgentTask("T-1", "synthetic-analysis", {"x": 1}))
    assert result.provider_id == "synthetic-agent"
    with pytest.raises(RuntimeContractError):
        runtime.run(
            AgentTask(
                "T-2",
                "over-budget",
                {},
                budget=ExecutionBudget(max_steps=1),
            )
        )


def test_p2_08_api_envelope_is_versioned_digest_bound_and_tamper_evident() -> None:
    envelope = ApiEnvelope.build(
        schema="lukart.case-result.v2",
        version="2.0.0",
        payload={"case_id": "SYN-1", "outcome": "ABSTAIN"},
    )
    decoded = ApiEnvelope.from_json(envelope.to_json())
    assert decoded == envelope
    tampered = json.loads(envelope.to_json())
    tampered["payload"]["outcome"] = "CONCLUDE"
    with pytest.raises(RuntimeContractError):
        ApiEnvelope.from_json(json.dumps(tampered))


def test_p2_09_cache_and_parallel_map_are_bounded_and_order_preserving() -> None:
    cache: LruArtifactCache[str, int] = LruArtifactCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    assert len(cache) == 2
    assert bounded_parallel_map(lambda value: value * value, (3, 1, 2), max_workers=2) == (
        9,
        1,
        4,
    )


def test_p2_10_plugin_registry_stores_classes_and_rejects_duplicates() -> None:
    registry: PluginRegistry[AgentProvider] = PluginRegistry()
    registry.register(SyntheticAgent)
    providers = registry.providers()
    assert providers == (SyntheticAgent,)
    assert isinstance(providers[0], type)
    assert registry.by_capability("synthetic-analysis") == (SyntheticAgent,)
    with pytest.raises(RuntimeContractError):
        registry.register(SyntheticAgent)
