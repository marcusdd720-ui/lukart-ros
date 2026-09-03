from __future__ import annotations

import pytest

from learning.semantic_self_healing import (
    ComponentDependency,
    ComponentDependencyGraph,
    ComponentNode,
    DiagnosisStatus,
    RevalidationMode,
    RootCauseCategory,
    SemanticFailureDiagnosis,
    plan_revalidation,
)

A = "a" * 64
B = "b" * 64


def _diagnosis(component_id: str | None) -> SemanticFailureDiagnosis:
    if component_id is None:
        return SemanticFailureDiagnosis(
            diagnosis_id="DX-stress-inconclusive",
            failure_digest=A,
            status=DiagnosisStatus.INCONCLUSIVE,
            root_cause=RootCauseCategory.UNKNOWN,
            target_component=None,
            rule_id=None,
            rationale="stress test intentionally preserves unknown root cause",
            evidence_digests=(B,),
        )
    return SemanticFailureDiagnosis(
        diagnosis_id=f"DX-stress-{component_id}",
        failure_digest=A,
        status=DiagnosisStatus.DIAGNOSED,
        root_cause=RootCauseCategory.REASONING,
        target_component=component_id,
        rule_id="RULE-STRESS-1",
        rationale="stress-test diagnosis",
        evidence_digests=(B,),
    )


def _node(index: int) -> ComponentNode:
    return ComponentNode(
        component_id=f"component-{index:02d}",
        validators=(f"validator-{index:02d}",),
    )


def test_complete_long_chain_selects_exact_downstream_closure() -> None:
    nodes = tuple(_node(index) for index in range(40))
    dependencies = tuple(
        ComponentDependency(
            upstream=f"component-{index:02d}",
            downstream=f"component-{index + 1:02d}",
        )
        for index in range(39)
    )
    graph = ComponentDependencyGraph(
        graph_version="stress-1",
        nodes=nodes,
        dependencies=dependencies,
        complete=True,
        completeness_evidence_digest=A,
    )

    plan = plan_revalidation(_diagnosis("component-17"), graph)

    assert plan.mode is RevalidationMode.SELECTIVE
    assert len(plan.impacted_components) == 23
    assert plan.impacted_components[0] == "component-17"
    assert plan.impacted_components[-1] == "component-39"
    assert len(plan.validators) == 23


def test_complete_branching_graph_propagates_to_every_descendant_only() -> None:
    nodes = tuple(_node(index) for index in range(8))
    dependencies = (
        ComponentDependency("component-00", "component-01"),
        ComponentDependency("component-00", "component-02"),
        ComponentDependency("component-01", "component-03"),
        ComponentDependency("component-01", "component-04"),
        ComponentDependency("component-02", "component-05"),
        ComponentDependency("component-05", "component-06"),
    )
    graph = ComponentDependencyGraph(
        graph_version="stress-2",
        nodes=nodes,
        dependencies=dependencies,
        complete=True,
        completeness_evidence_digest=A,
    )

    plan = plan_revalidation(_diagnosis("component-01"), graph)

    assert plan.mode is RevalidationMode.SELECTIVE
    assert plan.impacted_components == (
        "component-01",
        "component-03",
        "component-04",
    )
    assert "component-07" not in plan.impacted_components


def test_incomplete_large_graph_forces_broad_revalidation() -> None:
    nodes = tuple(_node(index) for index in range(50))
    graph = ComponentDependencyGraph(
        graph_version="stress-incomplete",
        nodes=nodes,
        dependencies=(),
        complete=False,
    )

    plan = plan_revalidation(_diagnosis("component-25"), graph)

    assert plan.mode is RevalidationMode.BROAD_REVALIDATION_REQUIRED
    assert len(plan.impacted_components) == 50
    assert len(plan.validators) == 50


def test_inconclusive_diagnosis_forces_broad_revalidation_even_with_complete_graph() -> None:
    nodes = tuple(_node(index) for index in range(12))
    graph = ComponentDependencyGraph(
        graph_version="stress-inconclusive",
        nodes=nodes,
        dependencies=(),
        complete=True,
        completeness_evidence_digest=A,
    )

    plan = plan_revalidation(_diagnosis(None), graph)

    assert plan.mode is RevalidationMode.BROAD_REVALIDATION_REQUIRED
    assert len(plan.impacted_components) == 12


def test_large_cycle_is_rejected_before_any_selective_plan_can_exist() -> None:
    nodes = tuple(_node(index) for index in range(20))
    dependencies = tuple(
        ComponentDependency(
            upstream=f"component-{index:02d}",
            downstream=f"component-{(index + 1) % 20:02d}",
        )
        for index in range(20)
    )

    with pytest.raises(ValueError, match="acyclic"):
        ComponentDependencyGraph(
            graph_version="stress-cycle",
            nodes=nodes,
            dependencies=dependencies,
            complete=True,
            completeness_evidence_digest=A,
        )
