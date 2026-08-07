"""
Legal queries over KnowledgeGraph.

Read-only facade over GraphQuery.
Does not mutate the graph.
Does not project, invent, or repair nodes.

Sections:
  1. Law catalogue (STATUTE / CASE_LAW)
  2. Case legal chain (Evidence → Fact → Issue → Argument)
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.query import GraphQuery
from knowledge.types import EdgeType, NodeType


def _sorted_nodes(nodes: list[KnowledgeNode]) -> list[KnowledgeNode]:
    return sorted(nodes, key=lambda n: n.id)


def _filter_type(
    nodes: list[KnowledgeNode],
    *allowed: NodeType,
) -> list[KnowledgeNode]:
    allowed_set = set(allowed)
    return _sorted_nodes([n for n in nodes if n.type in allowed_set])


class LegalQuery:
    """
    Read-only legal facade.

    Edge conventions:
      CASE_LAW --INTERPRETS--> STATUTE
      CASE_LAW --APPLIES-----> STATUTE
      CASE_LAW --CITES-------> STATUTE
      CASE/DECISION --RELIES_ON-----> STATUTE|CASE_LAW
      CASE/DECISION --SUPPORTED_BY--> CASE_LAW|STATUTE

      EVIDENCE --SUPPORTS--> FACT
      EVENT --REFERENCES--> EVIDENCE
      FACT --RAISES--> ISSUE
      ISSUE --RELIES_ON--> STATUTE | CASE_LAW
      ARGUMENT --ADVANCES--> ISSUE
      ISSUE --RESOLVES--> DECISION   (optional)
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self.q = GraphQuery(graph)

    def refresh(self) -> LegalQuery:
        """Rebuild GraphQuery indexes if the underlying graph changed."""
        self.q.refresh()
        return self

    # ------------------------------------------------------------------
    # 1. Law catalogue
    # ------------------------------------------------------------------

    def statutes(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.STATUTE))

    def case_law(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.CASE_LAW))

    def statute_by_article(self, article: str) -> list[KnowledgeNode]:
        article = article.strip()
        found = self.q.search(
            node_type=NodeType.STATUTE,
            metadata_key="article",
            metadata_value=article,
        )
        if found:
            return _sorted_nodes(found)
        return _sorted_nodes(
            self.q.search(node_type=NodeType.STATUTE, name_contains=article)
        )

    def interpretations_of(self, statute_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                statute_id, edge_type=EdgeType.INTERPRETS, direction="in"
            ),
            NodeType.CASE_LAW,
        )

    def statutes_interpreted_by(self, case_law_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                case_law_id, edge_type=EdgeType.INTERPRETS, direction="out"
            ),
            NodeType.STATUTE,
        )

    def applies(self, case_law_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                case_law_id, edge_type=EdgeType.APPLIES, direction="out"
            ),
            NodeType.STATUTE,
        )

    def cites(self, source_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(source_id, edge_type=EdgeType.CITES, direction="out")
        )

    def cited_by(self, target_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(target_id, edge_type=EdgeType.CITES, direction="in")
        )

    def relies_on(self, node_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(node_id, edge_type=EdgeType.RELIES_ON, direction="out")
        )

    def relied_on_by(self, node_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(node_id, edge_type=EdgeType.RELIES_ON, direction="in")
        )

    def supported_by(self, node_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(
                node_id, edge_type=EdgeType.SUPPORTED_BY, direction="out"
            )
        )

    def supports(self, authority_id: str) -> list[KnowledgeNode]:
        return _sorted_nodes(
            self.q.related(
                authority_id, edge_type=EdgeType.SUPPORTED_BY, direction="in"
            )
        )

    def authorities_for_statute(self, statute_id: str) -> list[KnowledgeNode]:
        """CASE_LAW useful for a statute: INTERPRETS + APPLIES + CITES (in)."""
        by_id: dict[str, KnowledgeNode] = {}
        for node in self.interpretations_of(statute_id):
            by_id[node.id] = node
        for node in self.q.related(
            statute_id, edge_type=EdgeType.APPLIES, direction="in"
        ):
            if node.type == NodeType.CASE_LAW:
                by_id[node.id] = node
        for node in self.cited_by(statute_id):
            if node.type == NodeType.CASE_LAW:
                by_id[node.id] = node
        return _sorted_nodes(list(by_id.values()))

    def case_law_for_article(self, article: str) -> list[KnowledgeNode]:
        """CASE_LAW interpreting/applying/citing statutes matching article."""
        by_id: dict[str, KnowledgeNode] = {}
        for statute in self.statute_by_article(article):
            for node in self.authorities_for_statute(statute.id):
                if node.type == NodeType.CASE_LAW:
                    by_id[node.id] = node
        return _sorted_nodes(list(by_id.values()))

    def case_law_text(self, case_law_id: str) -> str:
        """Plain text of a CASE_LAW node (description). Adapter, not a model field."""
        node = self.q.get(case_law_id)
        if node is None:
            return ""
        return (node.description or "").strip()

    # ------------------------------------------------------------------
    # 2. Case legal chain
    # ------------------------------------------------------------------

    def issues(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.ISSUE))

    def arguments(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.ARGUMENT))

    def facts(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.FACT))

    def evidence_nodes(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.EVIDENCE))

    def events(self) -> list[KnowledgeNode]:
        return _sorted_nodes(self.q.find_by_type(NodeType.EVENT))

    def issues_for_fact(self, fact_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(fact_id, edge_type=EdgeType.RAISES, direction="out"),
            NodeType.ISSUE,
        )

    def facts_raising(self, issue_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(issue_id, edge_type=EdgeType.RAISES, direction="in"),
            NodeType.FACT,
        )

    def issues_raised_by(self, fact_id: str) -> list[KnowledgeNode]:
        """Alias of issues_for_fact."""
        return self.issues_for_fact(fact_id)

    def authorities_for_issue(self, issue_id: str) -> list[KnowledgeNode]:
        """STATUTE | CASE_LAW that the Issue RELIES_ON."""
        return _filter_type(
            self.q.related(
                issue_id, edge_type=EdgeType.RELIES_ON, direction="out"
            ),
            NodeType.STATUTE,
            NodeType.CASE_LAW,
        )

    def arguments_for_issue(self, issue_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                issue_id, edge_type=EdgeType.ADVANCES, direction="in"
            ),
            NodeType.ARGUMENT,
        )

    def issue_for_argument(self, argument_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                argument_id, edge_type=EdgeType.ADVANCES, direction="out"
            ),
            NodeType.ISSUE,
        )

    def evidence_for_fact(self, fact_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                fact_id, edge_type=EdgeType.SUPPORTS, direction="in"
            ),
            NodeType.EVIDENCE,
        )

    def facts_for_evidence(self, evidence_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                evidence_id, edge_type=EdgeType.SUPPORTS, direction="out"
            ),
            NodeType.FACT,
        )

    def evidence_for_event(self, event_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                event_id, edge_type=EdgeType.REFERENCES, direction="out"
            ),
            NodeType.EVIDENCE,
        )

    def events_for_evidence(self, evidence_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                evidence_id, edge_type=EdgeType.REFERENCES, direction="in"
            ),
            NodeType.EVENT,
        )

    def resolves(self, issue_id: str) -> list[KnowledgeNode]:
        """ISSUE → DECISION (optional). Not used as legal authority."""
        return _sorted_nodes(
            self.q.related(
                issue_id, edge_type=EdgeType.RESOLVES, direction="out"
            )
        )

    def resolved_by(self, target_id: str) -> list[KnowledgeNode]:
        return _filter_type(
            self.q.related(
                target_id, edge_type=EdgeType.RESOLVES, direction="in"
            ),
            NodeType.ISSUE,
        )