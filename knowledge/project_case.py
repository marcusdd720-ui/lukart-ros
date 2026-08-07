"""
Single gateway: domain Case → KnowledgeGraph.

Deterministic projection order:
  1. Evidence
  2. Timeline
  3. Facts (+ SUPPORTS from Evidence)
  4. LegalIssues (+ RAISES / RELIES_ON from statute_refs + case_law_refs)
  5. Arguments (+ ADVANCES)
  6. Decisions (+ RESOLVES from Issue)

Primary authority source for ISSUE → law:
  LegalIssue.statute_refs
  LegalIssue.case_law_refs

legal_basis_ids = optional compatibility layer only.

Idempotent: project_case(X) ∘ project_case(X) ≡ project_case(X)

Legacy alias:
  project_case_issues = project_case
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.project_argument import project_argument
from knowledge.project_decision import project_decision
from knowledge.project_evidence import project_evidence
from knowledge.project_fact import project_fact
from knowledge.project_issue import project_legal_issue
from knowledge.project_timeline import project_timeline_event


def _resolve_authority_nodes(
    *,
    refs: list[str],
    authority_id_map: dict[str, str],
    graph: KnowledgeGraph,
    seen: set[str],
    out: list[str],
) -> None:
    for ref in refs:
        key = (ref or "").strip()
        if not key:
            continue
        node_id = authority_id_map.get(key, key)
        if node_id in seen:
            continue
        if graph.has_node(node_id):
            seen.add(node_id)
            out.append(node_id)


def project_case(
    graph: KnowledgeGraph,
    case: Case,
    *,
    fact_id_map: dict[str, str] | None = None,
    statute_id_map: dict[str, str] | None = None,
) -> list[str]:
    """
    Full domain → graph projection.

    statute_id_map (authority map) keys may be human refs or node ids:
      "art. 7 k.p.k." → "statute:kpk:7"
      "uchwała SN I KZP 6/13" → "caselaw:sn:I_KZP_6_13"
      "statute:kpk:7" → "statute:kpk:7"

    Returns list of ISSUE node ids.
    """
    for item in case.evidence_items:
        project_evidence(graph, item)

    for event in case.timeline_events:
        project_timeline_event(graph, event)

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

    authority_id_map = dict(statute_id_map or {})
    basis_by_id = {b.id: b for b in case.legal_bases}

    created: list[str] = []
    for issue in case.legal_issues:
        fact_nodes = [
            fact_id_map[fid] for fid in issue.fact_ids if fid in fact_id_map
        ]

        statute_nodes: list[str] = []
        seen: set[str] = set()

        _resolve_authority_nodes(
            refs=list(issue.statute_refs),
            authority_id_map=authority_id_map,
            graph=graph,
            seen=seen,
            out=statute_nodes,
        )
        _resolve_authority_nodes(
            refs=list(issue.case_law_refs),
            authority_id_map=authority_id_map,
            graph=graph,
            seen=seen,
            out=statute_nodes,
        )

        for bid in getattr(issue, "legal_basis_ids", None) or []:
            if bid in authority_id_map:
                node_id = authority_id_map[bid]
                if node_id not in seen and graph.has_node(node_id):
                    seen.add(node_id)
                    statute_nodes.append(node_id)
                continue
            basis = basis_by_id.get(bid)
            if basis is None:
                continue
            ref = (basis.reference or "").strip()
            if not ref:
                continue
            node_id = authority_id_map.get(ref, ref)
            if node_id not in seen and graph.has_node(node_id):
                seen.add(node_id)
                statute_nodes.append(node_id)

        node_id = project_legal_issue(
            graph,
            issue,
            fact_node_ids=fact_nodes or None,
            statute_node_ids=statute_nodes or None,
        )
        created.append(node_id)

    for argument in case.arguments:
        issue_node_id = f"issue:{argument.issue_id}"
        project_argument(
            graph,
            argument,
            issue_node_id=issue_node_id if graph.has_node(issue_node_id) else None,
        )

    for decision in case.decisions:
        project_decision(graph, decision)

    return created


# Backward-compatible alias (do not use in new code)
project_case_issues = project_case