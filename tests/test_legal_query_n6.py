"""N6 LegalQuery contract tests."""

from __future__ import annotations

from knowledge.models.case_workspace import open_ds_3960, open_ii_kp_459_26
from knowledge.types import NodeType


def test_query_does_not_mutate_graph() -> None:
    ws = open_ds_3960()
    n1, e1 = ws.graph.node_count(), ws.graph.edge_count()
    lq = ws.legal
    _ = lq.issues()
    _ = lq.arguments()
    _ = lq.facts()
    assert ws.graph.node_count() == n1
    assert ws.graph.edge_count() == e1


def test_missing_node_returns_empty() -> None:
    ws = open_ds_3960()
    lq = ws.legal
    assert lq.issues_for_fact("fact:does-not-exist") == []
    assert lq.authorities_for_issue("issue:does-not-exist") == []
    assert lq.arguments_for_issue("issue:does-not-exist") == []
    assert lq.evidence_for_fact("fact:does-not-exist") == []
    assert lq.facts_for_evidence("evidence:does-not-exist") == []


def test_type_filters() -> None:
    ws = open_ds_3960()
    lq = ws.legal
    for issue in lq.issues():
        for n in lq.authorities_for_issue(issue.id):
            assert n.type in (NodeType.STATUTE, NodeType.CASE_LAW)
        for n in lq.arguments_for_issue(issue.id):
            assert n.type == NodeType.ARGUMENT
        for n in lq.facts_raising(issue.id):
            assert n.type == NodeType.FACT
    for fact in lq.facts():
        for n in lq.issues_for_fact(fact.id):
            assert n.type == NodeType.ISSUE
        for n in lq.evidence_for_fact(fact.id):
            assert n.type == NodeType.EVIDENCE


def test_deterministic_order() -> None:
    ws = open_ds_3960()
    lq = ws.legal
    a = [n.id for n in lq.issues()]
    b = [n.id for n in lq.issues()]
    assert a == b
    assert a == sorted(a)


def test_case_isolation() -> None:
    ws_a = open_ds_3960()
    ws_b = open_ii_kp_459_26()
    ids_a = {n.id for n in ws_a.legal.issues()}
    ids_b = {n.id for n in ws_b.legal.issues()}
    assert ids_a.isdisjoint(ids_b)
    assert len(ids_a) == 3
    assert len(ids_b) == 2


def test_resolves_not_mixed_into_authorities() -> None:
    ws = open_ds_3960()
    lq = ws.legal
    for issue in lq.issues():
        auth_ids = {n.id for n in lq.authorities_for_issue(issue.id)}
        for n in lq.resolves(issue.id):
            assert n.id not in auth_ids or n.type in (
                NodeType.STATUTE,
                NodeType.CASE_LAW,
            )