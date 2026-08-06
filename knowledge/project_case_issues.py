"""
Project all LegalIssues from a domain Case into the KnowledgeGraph.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.project_issue import project_legal_issue


def project_case_issues(
    graph: KnowledgeGraph,
    case: Case,
    *,
    fact_id_map: dict[str, str] | None = None,
    statute_id_map: dict[str, str] | None = None,
) -> list[str]:
    """
    Project every LegalIssue of the domain Case into the graph.

    fact_id_map:     domain fact.id → graph fact node id
    statute_id_map:  domain legal_basis.id → graph statute node id
                     (or direct statute node ids)

    Returns list of created ISSUE node ids.
    """
    created: list[str] = []

    for issue in case.legal_issues:
        fact_nodes = []
        if fact_id_map:
            fact_nodes = [
                fact_id_map[fid]
                for fid in issue.fact_ids
                if fid in fact_id_map
            ]

        statute_nodes = []
        if statute_id_map:
            # prefer explicit legal_basis_ids mapping
            for bid in issue.legal_basis_ids:
                if bid in statute_id_map:
                    statute_nodes.append(statute_id_map[bid])
            # fallback: soft statute_refs that already look like node ids
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

    return created