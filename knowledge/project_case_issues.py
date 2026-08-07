"""
Project domain Case into KnowledgeGraph.

Order (deterministic):
  1. Evidence   → EVIDENCE
  2. Timeline   → EVENT
  3. Facts      → FACT
  4. LegalIssues → ISSUE + RAISES + RESOLVES
  5. Arguments   → ARGUMENT + ADVANCES

Idempotent: project(X) ∘ project(X) ≡ project(X)
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.project_argument import project_argument
from knowledge.project_evidence import project_evidence
from knowledge.project_fact import project_fact
from knowledge.project_issue import project_legal_issue
from knowledge.project_timeline import project_timeline_event


def project_case_issues(
    graph: KnowledgeGraph,
    case: Case,
    *,
    fact_id_map: dict[str, str] | None = None,
    statute_id_map: dict[str, str] | None = None,
) -> list[str]:
    """
    Full domain → graph projection.

    Returns list of ISSUE node ids.
    """
    # 0. Evidence
    for item in case.evidence_items:
        project_evidence(graph, item)

    # 1. Timeline
    for event in case.timeline_events:
        project_timeline_event(graph, event)

    # 2. Facts
    if fact_id_map is None:
        fact_id_map = {}
        for fact in case.facts:
            nid = project_fact(graph, fact)
            fact_id_map[fact.id] = nid
    else:
        domain_facts = {f.id: f for f in case.facts}
        for fid, gnid in list(fact_id_map.items()):
            if fid in domain_facts and not graph.has_node(gnid):
                fact_id_map[fid] = project_fact(graph, domain_facts[fid])

    # 3. Issues
    created: list[str] = []
    for issue in case.legal_issues:
        fact_nodes = [
            fact_id_map[fid]
            for fid in issue.fact_ids
            if fid in fact_id_map
        ]

        statute_nodes: list[str] = []
        if statute_id_map:
            for bid in issue.legal_basis_ids:
                if bid in statute_id_map:
                    statute_nodes.append(statute_id_map[bid])
            for ref in issue.statute_refs:
                if ref.startswith("statute:") and graph.has_node(ref):
                    statute_nodes.append(ref)

        node_id = project_legal_issue(
            graph,
            issue,
            fact_node_ids=fact_nodes or None,
            statute_node_ids=statute_nodes or None,
        )
        created.append(node_id)

    # 4. Arguments
    for argument in case.arguments:
        issue_node_id = f"issue:{argument.issue_id}"
        project_argument(
            graph,
            argument,
            issue_node_id=issue_node_id if graph.has_node(issue_node_id) else None,
        )

    return created