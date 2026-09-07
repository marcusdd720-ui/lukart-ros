from __future__ import annotations

from pathlib import Path

import pytest

from core.case_ledger.contracts import CaseId, ContentAddress
from core.semantic_change_v2 import (
    ArtifactKind,
    BlastRadiusExceeded,
    BlastRadiusReason,
    ImmutableArtifactRef,
    RecomputeLineageV2,
    SemanticChangeGraphV2,
    SemanticChangeV2Error,
    SemanticPropagationPolicyV2,
)


def _ref(
    case: CaseId,
    name: str,
    kind: ArtifactKind = ArtifactKind.PROJECTION,
) -> ImmutableArtifactRef:
    return ImmutableArtifactRef(
        case_id=case,
        kind=kind,
        identity=ContentAddress.for_value({"fixture": name}),
    )


def _chain(case: CaseId) -> tuple[
    ImmutableArtifactRef,
    ImmutableArtifactRef,
    ImmutableArtifactRef,
    ImmutableArtifactRef,
]:
    evidence = _ref(case, "evidence", ArtifactKind.EVIDENCE)
    epistemic = _ref(case, "epistemic")
    trust = _ref(case, "trust")
    result = _ref(case, "result", ArtifactKind.RESULT)
    return evidence, epistemic, trust, result


def _graph(case: CaseId) -> tuple[SemanticChangeGraphV2, tuple[ImmutableArtifactRef, ...]]:
    evidence, epistemic, trust, result = _chain(case)
    graph = SemanticChangeGraphV2(
        case_id=case,
        dependencies={
            evidence: (),
            epistemic: (evidence,),
            trust: (epistemic,),
            result: (trust,),
        },
    )
    return graph, (evidence, epistemic, trust, result)


def _policy(
    *,
    nodes: int = 100,
    depth: int = 100,
    work: int = 100,
) -> SemanticPropagationPolicyV2:
    return SemanticPropagationPolicyV2.build(
        max_nodes=nodes,
        max_depth=depth,
        max_work=work,
    )


def test_exact_immutable_change_propagates_deterministically() -> None:
    case = CaseId("CASE-PHX06-001")
    graph, refs = _graph(case)
    evidence, epistemic, trust, result = refs
    replay = ContentAddress.for_value({"replay": "exact"})

    first = graph.plan(
        (evidence,),
        policy=_policy(),
        replay_manifest_identity=replay,
    )
    second = graph.plan(
        (evidence,),
        policy=_policy(),
        replay_manifest_identity=replay,
    )

    assert first.affected == tuple(sorted(refs, key=lambda item: item.node_key))
    assert {item.affected for item in first.paths} == {evidence, epistemic, trust, result}
    assert first.plan_identity == second.plan_identity
    assert first.work_count == 3
    assert first.max_depth_observed == 3
    first.require_replay_manifest(replay)


def test_wrong_replay_manifest_identity_fails_closed() -> None:
    case = CaseId("CASE-PHX06-002")
    graph, refs = _graph(case)
    plan = graph.plan(
        (refs[0],),
        policy=_policy(),
        replay_manifest_identity=ContentAddress.for_value({"replay": "one"}),
    )

    with pytest.raises(SemanticChangeV2Error, match="replay identity mismatch"):
        plan.require_replay_manifest(ContentAddress.for_value({"replay": "two"}))


def test_cross_case_dependency_is_forbidden() -> None:
    left = CaseId("CASE-PHX06-A")
    right = CaseId("CASE-PHX06-B")
    source = _ref(left, "source")
    foreign = _ref(right, "foreign")

    with pytest.raises(SemanticChangeV2Error, match="cross-case"):
        SemanticChangeGraphV2(
            case_id=left,
            dependencies={source: (foreign,)},
        )


def test_self_dependency_fails_closed() -> None:
    case = CaseId("CASE-PHX06-SELF")
    source = _ref(case, "source")

    with pytest.raises(SemanticChangeV2Error, match="self dependency"):
        SemanticChangeGraphV2(case_id=case, dependencies={source: (source,)})


def test_cycle_reuses_existing_p3_fail_closed_graph_invariant() -> None:
    case = CaseId("CASE-PHX06-CYCLE")
    first = _ref(case, "first")
    second = _ref(case, "second")

    with pytest.raises(ValueError, match="cycle"):
        SemanticChangeGraphV2(
            case_id=case,
            dependencies={first: (second,), second: (first,)},
        )


def test_unknown_changed_ref_fails_closed() -> None:
    case = CaseId("CASE-PHX06-UNKNOWN")
    graph, _ = _graph(case)

    with pytest.raises(SemanticChangeV2Error, match="unknown changed immutable ref"):
        graph.plan(
            (_ref(case, "not-in-graph"),),
            policy=_policy(),
            replay_manifest_identity=ContentAddress.for_value({"replay": "unknown"}),
        )


def test_node_budget_is_hard_failure_without_truncation() -> None:
    case = CaseId("CASE-PHX06-NODES")
    graph, refs = _graph(case)

    with pytest.raises(BlastRadiusExceeded) as captured:
        graph.plan(
            (refs[0],),
            policy=_policy(nodes=2),
            replay_manifest_identity=ContentAddress.for_value({"replay": "nodes"}),
        )

    assert captured.value.reason is BlastRadiusReason.NODES
    assert "BLAST_RADIUS_EXCEEDED:NODES" in str(captured.value)


def test_depth_budget_is_hard_failure_without_truncation() -> None:
    case = CaseId("CASE-PHX06-DEPTH")
    graph, refs = _graph(case)

    with pytest.raises(BlastRadiusExceeded) as captured:
        graph.plan(
            (refs[0],),
            policy=_policy(depth=1),
            replay_manifest_identity=ContentAddress.for_value({"replay": "depth"}),
        )

    assert captured.value.reason is BlastRadiusReason.DEPTH
    assert captured.value.limit == 1


def test_work_budget_is_hard_failure_without_truncation() -> None:
    case = CaseId("CASE-PHX06-WORK")
    root = _ref(case, "root")
    left = _ref(case, "left")
    right = _ref(case, "right")
    graph = SemanticChangeGraphV2(
        case_id=case,
        dependencies={root: (), left: (root,), right: (root,)},
    )

    with pytest.raises(BlastRadiusExceeded) as captured:
        graph.plan(
            (root,),
            policy=_policy(work=1),
            replay_manifest_identity=ContentAddress.for_value({"replay": "work"}),
        )

    assert captured.value.reason is BlastRadiusReason.WORK
    assert captured.value.observed == 2


def test_materialize_paths_false_remains_bounded_and_deterministic() -> None:
    case = CaseId("CASE-PHX06-NOPATH")
    graph, refs = _graph(case)
    replay = ContentAddress.for_value({"replay": "no-path"})

    plan = graph.plan(
        (refs[0],),
        policy=_policy(),
        replay_manifest_identity=replay,
        materialize_paths=False,
    )

    assert plan.paths == ()
    assert len(plan.affected) == 4
    assert plan.work_count == 3


def test_recompute_lineage_creates_new_immutable_result_identity() -> None:
    case = CaseId("CASE-PHX06-LINEAGE")
    graph, refs = _graph(case)
    replay = ContentAddress.for_value({"replay": "lineage"})
    plan = graph.plan(
        (refs[0],),
        policy=_policy(),
        replay_manifest_identity=replay,
    )
    previous = ContentAddress.for_value({"result": "previous"})

    lineage = RecomputeLineageV2.build(
        plan=plan,
        previous_result_identity=previous,
        output={"result": "recomputed"},
    )

    lineage.verify()
    assert lineage.previous_result_identity == previous
    assert lineage.result_identity != previous
    assert lineage.plan_identity == plan.plan_identity
    assert lineage.replay_manifest_identity == replay


def test_same_content_still_has_lineage_bound_result_identity() -> None:
    case = CaseId("CASE-PHX06-SAME-CONTENT")
    graph, refs = _graph(case)
    plan = graph.plan(
        (refs[0],),
        policy=_policy(),
        replay_manifest_identity=ContentAddress.for_value({"replay": "same-content"}),
    )
    content = {"stable": True}
    content_identity = ContentAddress.for_value(content)
    previous = ContentAddress.for_value({"old-lineage": content_identity.canonical_dict()})

    lineage = RecomputeLineageV2.build(
        plan=plan,
        previous_result_identity=previous,
        output=content,
    )

    assert lineage.content_identity == content_identity
    assert lineage.result_identity != previous


def test_policy_is_content_addressed_and_tamper_evident() -> None:
    policy = _policy(nodes=10, depth=11, work=12)
    policy.verify()

    with pytest.raises(SemanticChangeV2Error, match="policy identity mismatch"):
        SemanticPropagationPolicyV2(
            max_nodes=10,
            max_depth=11,
            max_work=13,
            policy_identity=policy.policy_identity,
        )


def test_large_chain_fails_at_depth_budget_before_unbounded_traversal() -> None:
    case = CaseId("CASE-PHX06-LARGE")
    refs = tuple(_ref(case, f"node-{index}") for index in range(300))
    dependencies: dict[
        ImmutableArtifactRef, tuple[ImmutableArtifactRef, ...]
    ] = {refs[0]: ()}
    for index in range(1, len(refs)):
        dependencies[refs[index]] = (refs[index - 1],)
    graph = SemanticChangeGraphV2(case_id=case, dependencies=dependencies)

    with pytest.raises(BlastRadiusExceeded) as captured:
        graph.plan(
            (refs[0],),
            policy=_policy(nodes=500, depth=32, work=500),
            replay_manifest_identity=ContentAddress.for_value({"replay": "large"}),
            materialize_paths=False,
        )

    assert captured.value.reason is BlastRadiusReason.DEPTH


def test_v2_module_has_no_case_ledger_write_or_persistence_authority() -> None:
    source = Path("core/semantic_change_v2.py").read_text(encoding="utf-8")
    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
    assert "sqlite" not in source.lower()
