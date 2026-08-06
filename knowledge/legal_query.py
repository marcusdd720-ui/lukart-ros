"""
Legal queries over KnowledgeGraph (STATUTE / CASE_LAW / ISSUE).

Depends on GraphQuery + EdgeType legal relations from K1 + CASE-011.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.query import GraphQuery
from knowledge.types import EdgeType, NodeType


class LegalQuery:
    """
    Read-only legal facade.

    Edge conventions:
      CASE_LAW --INTERPRETS--> STATUTE
      CASE_LAW --APPLIES-----> STATUTE
      CASE_LAW --CITES-------> STATUTE
      CASE/DECISION --RELIES_ON-----> STATUTE|CASE_LAW
      CASE/DECISION --SUPPORTED_BY--> CASE_LAW|STATUTE

      # CASE-011
      FACT --RAISES--> ISSUE
      ISSUE --RESOLVES--> STATUTE | LAW | DECISION
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self.q = GraphQuery(graph)

    def refresh(self) -> LegalQuery:
        self.q.refresh()
        return self

    # ----- catalogues -----

    def statutes(self) -> list[KnowledgeNode]:
        return self.q.find_by_type(NodeType.STATUTE)

    def case_law(self) -> list[KnowledgeNode]:
        return self.q.find_by_type(NodeType.CASE_LAW)

    def issues(self) -> list[KnowledgeNode]:
        return self.q.find_by_type(NodeType.ISSUE)

    def statute_by_article(self, article: str) -> list[KnowledgeNode]:
        """Match metadata['article'] or name contains."""
        article = article.strip()
        found = self.q.search(
            node_type=NodeType.STATUTE,
            metadata_key="article",
            metadata_value=article,
        )
        if found:
            return found
        return self.q.search(node_type=NodeType.STATUTE, name_contains=article)

    # ----- CASE_LAW ↔ STATUTE -----

    def interpretations_of(self, statute_id: str) -> list[KnowledgeNode]:
        """CASE_LAW nodes that INTERPRET the statute."""
        return self.q.related(
            statute_id,
            edge_type=EdgeType.INTERPRETS,
            direction="in",
        )

    def statutes_interpreted_by(self, case_law_id: str) -> list[KnowledgeNode]:
        """STATUTE nodes interpreted by the judgment."""
        return self.q.related(
            case_law_id,
            edge_type=EdgeType.INTERPRETS,
            direction="out",
        )

    def applies(self, case_law_id: str) -> list[KnowledgeNode]:
        """STATUTE nodes applied by the judgment."""
        return self.q.related(
            case_law_id,
            edge_type=EdgeType.APPLIES,
            direction="out",
        )

    def cites(self, source_id: str) -> list[KnowledgeNode]:
        """Nodes cited by source (outgoing CITES)."""
        return self.q.related(
            source_id,
            edge_type=EdgeType.CITES,
            direction="out",
        )

    def cited_by(self, target_id: str) -> list[KnowledgeNode]:
        """Nodes that cite target (incoming CITES)."""
        return self.q.related(
            target_id,
            edge_type=EdgeType.CITES,
            direction="in",
        )

    # ----- Case / Decision support -----

    def relied_on_by(self, node_id: str) -> list[KnowledgeNode]:
        """Nodes that RELIES_ON this statute/case_law."""
        return self.q.related(
            node_id,
            edge_type=EdgeType.RELIES_ON,
            direction="in",
        )

    def relies_on(self, case_or_decision_id: str) -> list[KnowledgeNode]:
        return self.q.related(
            case_or_decision_id,
            edge_type=EdgeType.RELIES_ON,
            direction="out",
        )

    def supported_by(self, case_or_claim_id: str) -> list[KnowledgeNode]:
        return self.q.related(
            case_or_claim_id,
            edge_type=EdgeType.SUPPORTED_BY,
            direction="out",
        )

    def supports(self, authority_id: str) -> list[KnowledgeNode]:
        """Reverse of SUPPORTED_BY: what points to this authority."""
        return self.q.related(
            authority_id,
            edge_type=EdgeType.SUPPORTED_BY,
            direction="in",
        )

    # ----- ISSUE bridge (CASE-011) -----

    def issues_raised_by(self, fact_id: str) -> list[KnowledgeNode]:
        """ISSUE nodes raised by the given Fact (outgoing RAISES)."""
        return self.q.related(
            fact_id,
            edge_type=EdgeType.RAISES,
            direction="out",
        )

    def facts_raising(self, issue_id: str) -> list[KnowledgeNode]:
        """FACT nodes that raise the given Issue (incoming RAISES)."""
        return self.q.related(
            issue_id,
            edge_type=EdgeType.RAISES,
            direction="in",
        )

    def resolves(self, issue_id: str) -> list[KnowledgeNode]:
        """Nodes that the Issue resolves to (outgoing RESOLVES)."""
        return self.q.related(
            issue_id,
            edge_type=EdgeType.RESOLVES,
            direction="out",
        )

    def resolved_by(self, target_id: str) -> list[KnowledgeNode]:
        """ISSUE nodes that resolve to the given target (incoming RESOLVES)."""
        return self.q.related(
            target_id,
            edge_type=EdgeType.RESOLVES,
            direction="in",
        )

    # ----- convenience for pleadings -----

    def authorities_for_statute(self, statute_id: str) -> list[KnowledgeNode]:
        """
        Judgments useful for a statute:
        INTERPRETS + APPLIES (incoming to statute) + CITES (incoming).
        """
        by_id: dict[str, KnowledgeNode] = {}
        for node in self.interpretations_of(statute_id):
            by_id[node.id] = node
        for node in self.q.related(
            statute_id, edge_type=EdgeType.APPLIES, direction="in"
        ):
            by_id[node.id] = node
        for node in self.cited_by(statute_id):
            by_id[node.id] = node
        return list(by_id.values())

    def thesis(self, case_law_id: str) -> str:
        node = self.q.get(case_law_id)
        if node is None:
            return ""
        return (node.description or "").strip()