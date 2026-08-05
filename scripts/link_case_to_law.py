"""
K1.5 – Link a case node to STATUTE / CASE_LAW in the legal graph.
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


def link_ds_3960():
    graph = build_legal_graph()

    case_id = "case:DS.3960.2025"
    if not graph.has_node(case_id):
        case_node = KnowledgeNode(
            id=case_id,
            type=NodeType.CASE,
            name="DS.3960.2025",
            description=(
                "Postępowanie przygotowawcze – art. 284 § 2 k.k. "
                "(VW Transporter / darowizna)."
            ),
            metadata={
                "signature": "DS.3960.2025",
                "authority": "Prokuratura Rejonowa Poznań-Wilda",
            },
            tags={"case", "criminal", "ds3960"},
        )
        case_node.validate()
        graph.add_node(case_node)

    links: list[tuple[str, EdgeType, str]] = [
        (case_id, EdgeType.RELIES_ON, "statute:kk:284:2"),
        (case_id, EdgeType.RELIES_ON, "statute:kpk:17:1:2"),
        (case_id, EdgeType.RELIES_ON, "statute:kpk:7"),
        (case_id, EdgeType.RELIES_ON, "statute:kpk:410"),
        (case_id, EdgeType.SUPPORTED_BY, "caselaw:sn:V_KK_391_14"),
        (case_id, EdgeType.SUPPORTED_BY, "caselaw:sn:IV_KK_283_16"),
        (case_id, EdgeType.SUPPORTED_BY, "caselaw:sn:V_KK_491_17"),
        (case_id, EdgeType.SUPPORTED_BY, "caselaw:sn:II_KK_8_15"),
    ]

    for source, edge_type, target in links:
        if not graph.has_node(target):
            raise KeyError(f"Missing target node: {target}")
        edge = KnowledgeEdge(
            source=source,
            target=target,
            type=edge_type,
            description=f"{case_id} {edge_type.name} {target}",
            confidence=1.0,
        )
        edge.validate()
        graph.add_edge(edge)

    return graph, case_id


def main() -> None:
    graph, case_id = link_ds_3960()
    lq = LegalQuery(graph)

    print("Case linked:", case_id)
    print("nodes:", graph.node_count(), "edges:", graph.edge_count())
    print()
    print("RELIES_ON:")
    for n in lq.relies_on(case_id):
        print(" ", n.id, "|", n.name)
    print()
    print("SUPPORTED_BY:")
    for n in lq.supported_by(case_id):
        print(" ", n.id, "|", n.name)
    print()
    print("284 interpretations (library):")
    for n in lq.interpretations_of("statute:kk:284:2"):
        print(" ", n.id, "|", n.name)


if __name__ == "__main__":
    main()