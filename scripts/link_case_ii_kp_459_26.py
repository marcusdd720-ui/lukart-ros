"""
Link case II Kp 459/26 to STATUTE / CASE_LAW in the legal graph.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.edge import KnowledgeEdge
from knowledge.legal_query import LegalQuery
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType
from scripts.seed_legal_graph import build_legal_graph


def _ensure_statute_art16(graph) -> str:
    node_id = "statute:kpk:16"
    if graph.has_node(node_id):
        return node_id
    node = KnowledgeNode(
        id=node_id,
        type=NodeType.STATUTE,
        name="art. 16 k.p.k.",
        description=(
            "Obowiązek informacyjny organu procesowego; pouczenia powinny być "
            "udzielone w sposób zrozumiały dla uczestnika postępowania."
        ),
        metadata={"article": "16", "code": "k.p.k."},
        tags={"statute", "kpk", "pouczenia"},
    )
    node.validate()
    graph.add_node(node)
    return node_id


def _ensure_case_law_i_kzp_6_13(graph) -> str:
    node_id = "caselaw:sn:I_KZP_6_13"
    if graph.has_node(node_id):
        return node_id
    node = KnowledgeNode(
        id=node_id,
        type=NodeType.CASE_LAW,
        name="SN I KZP 6/13",
        description=(
            "Pouczenia mają charakter gwarancyjny; służą ochronie uczestnika "
            "nieprofesjonalnego i realizacji prawa do obrony / udziału w postępowaniu."
        ),
        metadata={"signature": "I KZP 6/13"},
        tags={"case_law", "sn", "pouczenia"},
    )
    node.validate()
    graph.add_node(node)

    art16 = _ensure_statute_art16(graph)
    edge = KnowledgeEdge(
        source=node_id,
        target=art16,
        type=EdgeType.INTERPRETS,
        description="I KZP 6/13 interprets art. 16 k.p.k.",
        confidence=1.0,
    )
    edge.validate()
    graph.add_edge(edge)
    return node_id


def link_ii_kp_459_26():
    graph = build_legal_graph()
    case_id = "case:II_Kp_459_26"

    if not graph.has_node(case_id):
        case_node = KnowledgeNode(
            id=case_id,
            type=NodeType.CASE,
            name="II Kp 459/26",
            description=(
                "Skarga na sposób wykonania obowiązku informacyjnego "
                "(Sąd Rejonowy w Wejherowie)."
            ),
            metadata={
                "signature": "II Kp 459/26",
                "prosecutor_ref": "4057-0.Ds.2517.2025",
                "court": "Sąd Rejonowy w Wejherowie",
            },
            tags={"case", "procedural", "ii_kp"},
        )
        case_node.validate()
        graph.add_node(case_node)

    art16 = _ensure_statute_art16(graph)
    kzp = _ensure_case_law_i_kzp_6_13(graph)

    links = [
        (case_id, EdgeType.RELIES_ON, art16),
        (case_id, EdgeType.SUPPORTED_BY, kzp),
    ]

    for source, edge_type, target in links:
        if not graph.has_node(target):
            raise KeyError(f"Missing target node: {target}")
        exists = any(
            e.source == source and e.target == target and e.type == edge_type
            for e in graph.edges
        )
        if exists:
            continue
        edge = KnowledgeEdge(
            source=source,
            target=target,
            type=edge_type,
            description=f"{source} {edge_type.name} {target}",
            confidence=1.0,
        )
        edge.validate()
        graph.add_edge(edge)

    return graph, case_id


def main() -> None:
    graph, case_id = link_ii_kp_459_26()
    lq = LegalQuery(graph)
    print("Case linked:", case_id)
    print("nodes:", graph.node_count(), "edges:", graph.edge_count())
    print("RELIES_ON:")
    for n in lq.relies_on(case_id):
        print(" ", n.id, "|", n.name)
    print("SUPPORTED_BY:")
    for n in lq.supported_by(case_id):
        print(" ", n.id, "|", n.name)


if __name__ == "__main__":
    main()