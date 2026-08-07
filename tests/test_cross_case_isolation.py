"""Cross-case isolation — DS vs II_Kp domain must not contaminate each other.

Shared STATUTE / CASE_LAW nodes from the legal knowledge base are expected.
Domain nodes and domain–domain edges must stay isolated.
"""

from __future__ import annotations

from knowledge.integrity_engine import IntegrityEngine
from knowledge.models.case_snapshot import compute_graph_hash
from knowledge.models.case_workspace import open_ds_3960, open_ii_kp_459_26
from knowledge.project_case import project_case
from knowledge.types import NodeType

DOMAIN_TYPES = {
    NodeType.FACT,
    NodeType.ISSUE,
    NodeType.ARGUMENT,
    NodeType.EVIDENCE,
    NodeType.EVENT,
    NodeType.DECISION,
    NodeType.CASE,
}


def _domain_ids(graph) -> set[str]:
    return {n.id for n in graph if n.type in DOMAIN_TYPES}


def test_separate_graph_objects() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    assert a.graph is not b.graph
    assert a.case is not b.case
    assert a.key != b.key


def test_domain_node_ids_disjoint() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    ids_a = _domain_ids(a.graph)
    ids_b = _domain_ids(b.graph)
    assert ids_a.isdisjoint(ids_b)
    assert ids_a
    assert ids_b


def test_law_nodes_excluded_from_domain_isolation() -> None:
    """Law KB may overlap; must not be treated as domain contamination."""
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    law = {NodeType.STATUTE, NodeType.CASE_LAW}
    domain_a = _domain_ids(a.graph)
    domain_b = _domain_ids(b.graph)
    law_a = {n.id for n in a.graph if n.type in law}
    law_b = {n.id for n in b.graph if n.type in law}
    assert domain_a.isdisjoint(domain_b)
    # law ids are allowed to intersect domain of neither isolation set
    assert not (law_a & domain_a & domain_b)
    assert not (law_b & domain_a & domain_b)


def test_issue_sets_disjoint() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    ia = {n.id for n in a.graph if n.type == NodeType.ISSUE}
    ib = {n.id for n in b.graph if n.type == NodeType.ISSUE}
    assert ia.isdisjoint(ib)
    assert len(ia) == 3
    assert len(ib) == 2


def test_no_cross_case_domain_edges() -> None:
    """No edge may connect domain node of A with domain node of B.

    Each workspace has its own graph object, so this is a safety net:
    domain endpoints of any edge in A must not appear in B's domain set.
    """
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    ids_a = _domain_ids(a.graph)
    ids_b = _domain_ids(b.graph)

    for e in a.graph.edges:
        src, tgt = e.source, e.target
        if src in ids_a:
            assert src not in ids_b
        if tgt in ids_a:
            assert tgt not in ids_b

    for e in b.graph.edges:
        src, tgt = e.source, e.target
        if src in ids_b:
            assert src not in ids_a
        if tgt in ids_b:
            assert tgt not in ids_a


def test_hashes_differ_and_stable() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    ha = compute_graph_hash(a.graph)
    hb = compute_graph_hash(b.graph)
    assert ha != hb
    assert ha == compute_graph_hash(open_ds_3960().graph)
    assert hb == compute_graph_hash(open_ii_kp_459_26().graph)


def test_integrity_independent() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    ra = IntegrityEngine.run(a.graph, a.case)
    rb = IntegrityEngine.run(b.graph, b.case)
    assert not ra.blocks
    assert not rb.blocks


def test_mutation_isolation() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    n_b = b.graph.node_count()
    e_b = b.graph.edge_count()
    hb_before = compute_graph_hash(b.graph)

    # idempotent re-project of A must not touch B
    project_case(a.graph, a.case)

    assert b.graph.node_count() == n_b
    assert b.graph.edge_count() == e_b
    assert compute_graph_hash(b.graph) == hb_before