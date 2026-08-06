"""
Project all LegalIssues and Arguments from a domain Case into the KnowledgeGraph.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.project_argument import project_argument
from knowledge.project_issue import project_legal_issue


def project_case_issues(
    graph: KnowledgeGraph,
    case: Case,
    *,
    fact_id_map: dict[str, str] | None = None,
    statute_id_map: dict[str, str] | None = None,
) -> list[str]:
    """
    Project every LegalIssue of the domain Case into the graph,
    then every Argument (ADVANCES → Issue).

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

    # Arguments → ADVANCES → Issue
    for argument in case.arguments:
        issue_node_id = f"issue:{argument.issue_id}"
        project_argument(
            graph,
            argument,
            issue_node_id=issue_node_id if graph.has_node(issue_node_id) else None,
        )

    return created