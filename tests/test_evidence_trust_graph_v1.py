from __future__ import annotations

from pathlib import Path

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, ObjectId
from core.p3.contracts import RuntimeIdentity
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicLedgerService, EvidenceEventRef
from knowledge.evidence_trust_graph import (
    TRUST_RELATION_EVENT_V1,
    EvidenceTrustGraph,
    EvidenceTrustGraphError,
    TrustEdgeType,
    TrustPolicyV1,
    TrustRelationDeclaration,
    assertion_node_id,
    event_node_id,
)


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="trust-graph.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        provider_inventory_declared=True,
    )


def _ledger(tmp_path: Path) -> CanonicalCaseLedger:
    return CanonicalCaseLedger(tmp_path / "canonical.db")


def _append_event(
    ledger: CanonicalCaseLedger,
    case_id: CaseId,
    *,
    event_type: str,
    payload: dict[str, object],
) -> ContentAddress:
    event = ledger.append_event(
        case_id=case_id,
        event_type=event_type,
        runtime_identity=_runtime(),
        payload=payload,
        expected_head=ledger.head(case_id),
    )
    return event.event_id


def _claim(
    service: EpistemicLedgerService,
    ledger: CanonicalCaseLedger,
    case_id: CaseId,
    *,
    object_id: str,
) -> ContentAddress:
    assertion = service.create_assertion(
        case_id=case_id,
        subject_id=ObjectId(object_id),
        assertion_type="claim.v1",
        content={"value": object_id},
        initial_status=KnowledgeStatus.CLAIM,
        evidence_refs=(),
        runtime_identity=_runtime(),
        expected_head=ledger.head(case_id),
    )
    return assertion.assertion_id


def _graph(
    ledger: CanonicalCaseLedger,
    service: EpistemicLedgerService,
    case_id: CaseId,
    *,
    policy: TrustPolicyV1 | None = None,
) -> EvidenceTrustGraph:
    return EvidenceTrustGraph.build(
        case_id=case_id,
        events=ledger.events(case_id),
        epistemic_projection=service.project(case_id),
        policy=policy or TrustPolicyV1.reference(),
    )


def _bounded_policy(*, max_nodes: int, max_edges: int) -> TrustPolicyV1:
    edges = (
        TrustEdgeType.ATTESTED_BY,
        TrustEdgeType.AUTHORIZED_BY,
        TrustEdgeType.CONTRADICTS,
    )
    body = TrustPolicyV1._body(
        allowed_explicit_edges=edges,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )
    return TrustPolicyV1(
        allowed_explicit_edges=edges,
        max_nodes=max_nodes,
        max_edges=max_edges,
        policy_identity=ContentAddress.for_value(body),
    )


def test_graph_is_deterministic_and_bound_to_exact_ledger_and_epistemic_projection(
    tmp_path: Path,
) -> None:
    case_id = CaseId("CASE-TRUST-001")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        _claim(service, ledger, case_id, object_id="OBJ-1")

        first = _graph(ledger, service, case_id)
        second = _graph(ledger, service, case_id)

        assert first == second
        assert first.graph_identity == second.graph_identity
        assert first.ledger_head == ledger.head(case_id)
        assert first.epistemic_projection_identity == service.project(case_id).projection_identity
        first.verify()


def test_exact_fact_evidence_is_represented_as_support_edge(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-FACT")
    with _ledger(tmp_path) as ledger:
        evidence_id = _append_event(
            ledger,
            case_id,
            event_type="evidence.ingested.v1",
            payload={"digest": "d" * 64},
        )
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-FACT"),
            assertion_type="fact.v1",
            content={"value": 1},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(EvidenceEventRef(case_id=case_id, event_id=evidence_id),),
            runtime_identity=_runtime(),
            expected_head=evidence_id,
        )

        graph = _graph(ledger, service, case_id)
        support = [edge for edge in graph.edges if edge.edge_type is TrustEdgeType.SUPPORTS]

        assert len(support) == 1
        assert support[0].source_node_id == event_node_id(evidence_id)
        assert support[0].target_node_id == assertion_node_id(assertion.assertion_id)


def test_contradiction_exists_only_after_explicit_canonical_relation(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-CONTRADICTION")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        left = _claim(service, ledger, case_id, object_id="OBJ-LEFT")
        right = _claim(service, ledger, case_id, object_id="OBJ-RIGHT")

        before = _graph(ledger, service, case_id)
        assert not any(edge.edge_type is TrustEdgeType.CONTRADICTS for edge in before.edges)

        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.CONTRADICTS,
            source_node_id=assertion_node_id(left),
            target_node_id=assertion_node_id(right),
        )
        _append_event(
            ledger,
            case_id,
            event_type=TRUST_RELATION_EVENT_V1,
            payload={"relation": relation.canonical_dict()},
        )

        after = _graph(ledger, service, case_id)
        contradictions = [
            edge for edge in after.edges if edge.edge_type is TrustEdgeType.CONTRADICTS
        ]
        assert len(contradictions) == 1


def test_attestation_is_provenance_edge_not_epistemic_promotion(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-ATTEST")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion_id = _claim(service, ledger, case_id, object_id="OBJ-CLAIM")
        attestation_id = _append_event(
            ledger,
            case_id,
            event_type="attestation.verified.v1",
            payload={"issuer": "fixture", "valid": True},
        )
        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.ATTESTED_BY,
            source_node_id=assertion_node_id(assertion_id),
            target_node_id=event_node_id(attestation_id),
        )
        _append_event(
            ledger,
            case_id,
            event_type=TRUST_RELATION_EVENT_V1,
            payload={"relation": relation.canonical_dict()},
        )

        graph = _graph(ledger, service, case_id)
        state = service.project(case_id).get(assertion_id)

        assert any(edge.edge_type is TrustEdgeType.ATTESTED_BY for edge in graph.edges)
        assert state is not None
        assert state.status is KnowledgeStatus.CLAIM


def test_authorization_relation_is_explicit_and_does_not_create_truth(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-AUTH")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion_id = _claim(service, ledger, case_id, object_id="OBJ-AUTH")
        auth_event = _append_event(
            ledger,
            case_id,
            event_type="authorization.decision.v1",
            payload={"decision": "allow", "scope": "case"},
        )
        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.AUTHORIZED_BY,
            source_node_id=assertion_node_id(assertion_id),
            target_node_id=event_node_id(auth_event),
        )
        _append_event(
            ledger,
            case_id,
            event_type=TRUST_RELATION_EVENT_V1,
            payload={"relation": relation.canonical_dict()},
        )

        graph = _graph(ledger, service, case_id)
        assert any(edge.edge_type is TrustEdgeType.AUTHORIZED_BY for edge in graph.edges)
        state = service.project(case_id).get(assertion_id)
        assert state is not None and state.status is KnowledgeStatus.CLAIM


def test_cross_case_or_dangling_relation_fails_closed(tmp_path: Path) -> None:
    case_a = CaseId("CASE-TRUST-A")
    case_b = CaseId("CASE-TRUST-B")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion_id = _claim(service, ledger, case_a, object_id="OBJ-A")
        foreign_event = _append_event(
            ledger,
            case_b,
            event_type="attestation.verified.v1",
            payload={"issuer": "foreign"},
        )
        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.ATTESTED_BY,
            source_node_id=assertion_node_id(assertion_id),
            target_node_id=event_node_id(foreign_event),
        )
        _append_event(
            ledger,
            case_a,
            event_type=TRUST_RELATION_EVENT_V1,
            payload={"relation": relation.canonical_dict()},
        )

        with pytest.raises(EvidenceTrustGraphError, match="unknown node"):
            _graph(ledger, service, case_a)


def test_unknown_trust_event_fails_closed(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-UNKNOWN")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        _append_event(
            ledger,
            case_id,
            event_type="trust.future.v99",
            payload={"future": True},
        )

        with pytest.raises(EvidenceTrustGraphError, match="unknown trust event type"):
            _graph(ledger, service, case_id)


def test_tampered_relation_identity_is_rejected(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-TAMPER")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        left = _claim(service, ledger, case_id, object_id="OBJ-L")
        right = _claim(service, ledger, case_id, object_id="OBJ-R")
        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.CONTRADICTS,
            source_node_id=assertion_node_id(left),
            target_node_id=assertion_node_id(right),
        ).canonical_dict()
        relation["target_node_id"] = assertion_node_id(left)
        _append_event(
            ledger,
            case_id,
            event_type=TRUST_RELATION_EVENT_V1,
            payload={"relation": relation},
        )

        with pytest.raises(EvidenceTrustGraphError):
            _graph(ledger, service, case_id)


def test_duplicate_semantic_explicit_relation_is_rejected(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-DUP")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        left = _claim(service, ledger, case_id, object_id="OBJ-L")
        right = _claim(service, ledger, case_id, object_id="OBJ-R")
        relation = TrustRelationDeclaration.build(
            edge_type=TrustEdgeType.CONTRADICTS,
            source_node_id=assertion_node_id(left),
            target_node_id=assertion_node_id(right),
        )
        for _ in range(2):
            _append_event(
                ledger,
                case_id,
                event_type=TRUST_RELATION_EVENT_V1,
                payload={"relation": relation.canonical_dict()},
            )

        with pytest.raises(EvidenceTrustGraphError, match="duplicate semantic"):
            _graph(ledger, service, case_id)


def test_stale_epistemic_projection_is_rejected(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-STALE")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        _claim(service, ledger, case_id, object_id="OBJ-1")
        stale = service.project(case_id)
        _append_event(
            ledger,
            case_id,
            event_type="evidence.ingested.v1",
            payload={"digest": "e" * 64},
        )

        with pytest.raises(EvidenceTrustGraphError, match="ledger head is stale"):
            EvidenceTrustGraph.build(
                case_id=case_id,
                events=ledger.events(case_id),
                epistemic_projection=stale,
                policy=TrustPolicyV1.reference(),
            )


def test_graph_identity_changes_with_policy_identity(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-POLICY")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        _claim(service, ledger, case_id, object_id="OBJ-P")
        broad = TrustPolicyV1.reference()
        bounded = _bounded_policy(max_nodes=100, max_edges=100)

        first = _graph(ledger, service, case_id, policy=broad)
        second = _graph(ledger, service, case_id, policy=bounded)

        assert first.trust_policy_identity != second.trust_policy_identity
        assert first.graph_identity != second.graph_identity


def test_node_and_edge_budgets_fail_instead_of_truncating(tmp_path: Path) -> None:
    case_id = CaseId("CASE-TRUST-BOUNDS")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        _claim(service, ledger, case_id, object_id="OBJ-B")

        with pytest.raises(EvidenceTrustGraphError, match="NODE_LIMIT_EXCEEDED"):
            _graph(
                ledger,
                service,
                case_id,
                policy=_bounded_policy(max_nodes=1, max_edges=100),
            )

    edge_case = CaseId("CASE-TRUST-EDGE-BOUNDS")
    with _ledger(tmp_path) as ledger:
        evidence_id = _append_event(
            ledger,
            edge_case,
            event_type="evidence.ingested.v1",
            payload={"digest": "f" * 64},
        )
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=edge_case,
            subject_id=ObjectId("OBJ-F"),
            assertion_type="fact.v1",
            content={"value": 1},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(EvidenceEventRef(case_id=edge_case, event_id=evidence_id),),
            runtime_identity=_runtime(),
            expected_head=evidence_id,
        )

        with pytest.raises(EvidenceTrustGraphError, match="EDGE_LIMIT_EXCEEDED"):
            _graph(
                ledger,
                service,
                edge_case,
                policy=_bounded_policy(max_nodes=100, max_edges=1),
            )


def test_trust_graph_module_has_no_canonical_ledger_write_path() -> None:
    source = Path("knowledge/evidence_trust_graph.py").read_text(encoding="utf-8")
    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
