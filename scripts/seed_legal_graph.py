"""
K1.3 – Seed legal knowledge into KnowledgeGraph.

STATUTE + CASE_LAW nodes and legal edges:
  INTERPRETS, APPLIES, CITES, RELIES_ON, SUPPORTED_BY
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def _statute(
    node_id: str,
    name: str,
    *,
    code: str,
    article: str,
    description: str,
) -> KnowledgeNode:
    return KnowledgeNode(
        id=node_id,
        type=NodeType.STATUTE,
        name=name,
        description=description,
        metadata={
            "code": code,
            "article": article,
            "jurisdiction": "PL",
        },
        tags=["law", "statute", code.lower()],
    )


def _case_law(
    node_id: str,
    name: str,
    *,
    court: str,
    date: str,
    signature: str,
    thesis: str,
) -> KnowledgeNode:
    return KnowledgeNode(
        id=node_id,
        type=NodeType.CASE_LAW,
        name=name,
        description=thesis,
        metadata={
            "court": court,
            "date": date,
            "signature": signature,
            "jurisdiction": "PL",
        },
        tags=["law", "case_law", "sn"],
    )


def _edge(
    source: str,
    target: str,
    edge_type: EdgeType,
    description: str = "",
) -> KnowledgeEdge:
    return KnowledgeEdge(
        source=source,
        target=target,
        type=edge_type,
        description=description,
        confidence=1.0,
    )


def build_legal_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()

    # ----- STATUTES -----
    statutes = [
        _statute(
            "statute:kk:284:2",
            "art. 284 § 2 k.k.",
            code="k.k.",
            article="284 § 2",
            description=(
                "Przywłaszczenie rzeczy powierzonej. Wymaga m.in. powierzenia "
                "z obowiązkiem zwrotu oraz zamiaru bezpośredniego przywłaszczenia."
            ),
        ),
        _statute(
            "statute:kpk:7",
            "art. 7 k.p.k.",
            code="k.p.k.",
            article="7",
            description=(
                "Swobodna ocena dowodów – organ ocenia dowody według własnego "
                "przekonania, z uwzględnieniem zasad prawidłowego rozumowania."
            ),
        ),
        _statute(
            "statute:kpk:410",
            "art. 410 k.p.k.",
            code="k.p.k.",
            article="410",
            description=(
                "Podstawę wyroku stanowi całokształt okoliczności ujawnionych "
                "w toku rozprawy głównej."
            ),
        ),
        _statute(
            "statute:kpk:17:1:2",
            "art. 17 § 1 pkt 2 k.p.k.",
            code="k.p.k.",
            article="17 § 1 pkt 2",
            description=(
                "Nie wszczyna się postępowania, a wszczęte umarza, gdy czyn "
                "nie zawiera znamion czynu zabronionego."
            ),
        ),
        _statute(
            "statute:kpk:5:2",
            "art. 5 § 2 k.p.k.",
            code="k.p.k.",
            article="5 § 2",
            description=(
                "Niedające się usunąć wątpliwości rozstrzyga się na korzyść "
                "oskarżonego."
            ),
        ),
    ]

    # ----- CASE LAW -----
    cases = [
        _case_law(
            "caselaw:sn:V_KK_391_14",
            "SN V KK 391/14",
            court="Sąd Najwyższy",
            date="2015-02-17",
            signature="V KK 391/14",
            thesis=(
                "Powierzenie rzeczy polega na przekazaniu sprawcy władztwa "
                "nad rzeczą z obowiązkiem jej zwrotu."
            ),
        ),
        _case_law(
            "caselaw:sn:IV_KK_283_16",
            "SN IV KK 283/16",
            court="Sąd Najwyższy",
            date="2017-01-11",
            signature="IV KK 283/16",
            thesis=(
                "Odpowiedzialność z art. 284 § 2 k.k. dotyczy rzeczy powierzonej "
                "i wymaga ustalenia stosunku powierzenia oraz zamiaru "
                "bezpośredniego przywłaszczenia."
            ),
        ),
        _case_law(
            "caselaw:sn:V_KK_491_17",
            "SN V KK 491/17",
            court="Sąd Najwyższy",
            date="2018-01-16",
            signature="V KK 491/17",
            thesis=(
                "Naruszenie art. 410 k.p.k. zachodzi, gdy rozstrzygnięcie opiera "
                "się na materiale nieujawnionym albo jedynie na części materiału "
                "ujawnionego."
            ),
        ),
        _case_law(
            "caselaw:sn:II_KK_8_15",
            "SN II KK 8/15",
            court="Sąd Najwyższy",
            date="2015-02-18",
            signature="II KK 8/15",
            thesis=(
                "Swobodna ocena dowodów nie jest oceną dowolną; wymaga oparcia "
                "na całokształcie dowodów i zasadach prawidłowego rozumowania."
            ),
        ),
    ]

    for node in statutes + cases:
        node.validate()
        g.add_node(node)

    # ----- EDGES: case law → statute -----
    edges = [
        _edge(
            "caselaw:sn:V_KK_391_14",
            "statute:kk:284:2",
            EdgeType.INTERPRETS,
            "Definicja powierzenia przy 284 § 2 k.k.",
        ),
        _edge(
            "caselaw:sn:IV_KK_283_16",
            "statute:kk:284:2",
            EdgeType.INTERPRETS,
            "Znamiona: powierzenie + zamiar bezpośredni",
        ),
        _edge(
            "caselaw:sn:V_KK_491_17",
            "statute:kpk:410",
            EdgeType.INTERPRETS,
            "Całokształt ujawnionych okoliczności",
        ),
        _edge(
            "caselaw:sn:II_KK_8_15",
            "statute:kpk:7",
            EdgeType.INTERPRETS,
            "Swobodna vs dowolna ocena dowodów",
        ),
        _edge(
            "caselaw:sn:V_KK_391_14",
            "statute:kpk:7",
            EdgeType.CITES,
            "Ocena zamiaru w świetle całokształtu",
        ),
        _edge(
            "caselaw:sn:IV_KK_283_16",
            "statute:kpk:410",
            EdgeType.APPLIES,
            "Ocena znamion na podstawie całokształtu materiału",
        ),
    ]

    for edge in edges:
        edge.validate()
        g.add_edge(edge)

    return g


def main() -> None:
    graph = build_legal_graph()
    statutes = [n for n in graph if n.type == NodeType.STATUTE]
    case_law = [n for n in graph if n.type == NodeType.CASE_LAW]

    print("Legal graph seed")
    print(f"  nodes:     {graph.node_count()}")
    print(f"  edges:     {graph.edge_count()}")
    print(f"  STATUTE:   {len(statutes)}")
    print(f"  CASE_LAW:  {len(case_law)}")
    print()
    print("STATUTE:")
    for n in statutes:
        print(f"  - {n.id}  |  {n.name}")
    print()
    print("CASE_LAW:")
    for n in case_law:
        print(f"  - {n.id}  |  {n.name}")
    print()
    print("EDGES:")
    for e in graph.edges:
        print(f"  - {e.source}  --{e.type.name}-->  {e.target}")


if __name__ == "__main__":
    main()
