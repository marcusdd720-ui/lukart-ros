"""PHX-04 deterministic Evidence Trust Graph over CCL and Epistemic v2.

The graph is a content-addressed projection, never a writable authority. Canonical
Case Ledger remains the only authoritative case-history write path. Contradiction,
authorization and attestation edges exist only when explicitly recorded as canonical
trust-relation events; the graph never infers them from model output or metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.case_ledger.contracts import CaseId, ContentAddress, LedgerEvent
from knowledge.epistemic_assertions import (
    ASSERTION_CREATED_EVENT_V1,
    ASSERTION_TRANSITION_EVENT_V1,
    Assertion,
    EpistemicDecisionV2,
    EpistemicProjectionV2,
)

TRUST_POLICY_SCHEMA_V1 = "lukart.evidence-trust-policy.v1"
TRUST_RELATION_SCHEMA_V1 = "lukart.evidence-trust-relation.v1"
TRUST_GRAPH_SCHEMA_V1 = "lukart.evidence-trust-graph.v1"
TRUST_RELATION_EVENT_V1 = "trust.relation.declared.v1"
DEFAULT_MAX_TRUST_NODES = 20_000
DEFAULT_MAX_TRUST_EDGES = 40_000


class EvidenceTrustGraphError(ValueError):
    """Fail-closed Evidence Trust Graph contract violation."""


class TrustNodeKind(StrEnum):
    EVENT = "EVENT"
    ASSERTION = "ASSERTION"
    DECISION = "DECISION"


class TrustEdgeType(StrEnum):
    SUPPORTS = "SUPPORTS"
    TRANSITIONS = "TRANSITIONS"
    RECORDED_BY = "RECORDED_BY"
    CONTRADICTS = "CONTRADICTS"
    AUTHORIZED_BY = "AUTHORIZED_BY"
    ATTESTED_BY = "ATTESTED_BY"


def event_node_id(event_id: ContentAddress) -> str:
    return f"event:{event_id}"


def assertion_node_id(assertion_id: ContentAddress) -> str:
    return f"assertion:{assertion_id}"


def decision_node_id(decision_id: ContentAddress) -> str:
    return f"decision:{decision_id}"


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise EvidenceTrustGraphError(f"{field_name} must be nonblank and canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise EvidenceTrustGraphError(f"{field_name} cannot contain control characters")
    return value


@dataclass(frozen=True, slots=True)
class TrustPolicyV1:
    allowed_explicit_edges: tuple[TrustEdgeType, ...]
    max_nodes: int
    max_edges: int
    policy_identity: ContentAddress
    schema: str = TRUST_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != TRUST_POLICY_SCHEMA_V1:
            raise EvidenceTrustGraphError(f"unsupported trust policy schema: {self.schema}")
        if self.max_nodes < 1 or self.max_edges < 1:
            raise EvidenceTrustGraphError("trust graph bounds must be positive")
        normalized = tuple(sorted(set(self.allowed_explicit_edges), key=lambda item: item.value))
        forbidden = {
            TrustEdgeType.SUPPORTS,
            TrustEdgeType.TRANSITIONS,
            TrustEdgeType.RECORDED_BY,
        }
        if not normalized or any(edge in forbidden for edge in normalized):
            raise EvidenceTrustGraphError("explicit trust-edge policy contains invalid edge type")
        object.__setattr__(self, "allowed_explicit_edges", normalized)
        self.verify()

    @classmethod
    def reference(cls) -> TrustPolicyV1:
        edges = (
            TrustEdgeType.ATTESTED_BY,
            TrustEdgeType.AUTHORIZED_BY,
            TrustEdgeType.CONTRADICTS,
        )
        body = cls._body(
            allowed_explicit_edges=edges,
            max_nodes=DEFAULT_MAX_TRUST_NODES,
            max_edges=DEFAULT_MAX_TRUST_EDGES,
        )
        return cls(
            allowed_explicit_edges=edges,
            max_nodes=DEFAULT_MAX_TRUST_NODES,
            max_edges=DEFAULT_MAX_TRUST_EDGES,
            policy_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        allowed_explicit_edges: tuple[TrustEdgeType, ...],
        max_nodes: int,
        max_edges: int,
    ) -> dict[str, object]:
        return {
            "schema": TRUST_POLICY_SCHEMA_V1,
            "allowed_explicit_edges": sorted(edge.value for edge in allowed_explicit_edges),
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "authority": "projection-only",
            "attestation_semantics": "origin-integrity-evidence-not-epistemic-truth",
            "cross_case_edges": "deny",
            "unknown_trust_event": "fail",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            allowed_explicit_edges=self.allowed_explicit_edges,
            max_nodes=self.max_nodes,
            max_edges=self.max_edges,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "policy_identity": self.policy_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.policy_identity != ContentAddress.for_value(self.canonical_body()):
            raise EvidenceTrustGraphError("trust policy identity mismatch")


@dataclass(frozen=True, slots=True)
class TrustRelationDeclaration:
    edge_type: TrustEdgeType
    source_node_id: str
    target_node_id: str
    relation_identity: ContentAddress
    schema: str = TRUST_RELATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != TRUST_RELATION_SCHEMA_V1:
            raise EvidenceTrustGraphError(
                f"unsupported trust relation schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "source_node_id",
            _identifier(self.source_node_id, field_name="source_node_id"),
        )
        object.__setattr__(
            self,
            "target_node_id",
            _identifier(self.target_node_id, field_name="target_node_id"),
        )
        if self.source_node_id == self.target_node_id:
            raise EvidenceTrustGraphError("trust relation self-loop is forbidden")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        edge_type: TrustEdgeType,
        source_node_id: str,
        target_node_id: str,
    ) -> TrustRelationDeclaration:
        source = _identifier(source_node_id, field_name="source_node_id")
        target = _identifier(target_node_id, field_name="target_node_id")
        body = {
            "schema": TRUST_RELATION_SCHEMA_V1,
            "edge_type": edge_type.value,
            "source_node_id": source,
            "target_node_id": target,
        }
        return cls(
            edge_type=edge_type,
            source_node_id=source,
            target_node_id=target,
            relation_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> TrustRelationDeclaration:
        schema = value.get("schema")
        raw_type = value.get("edge_type")
        source = value.get("source_node_id")
        target = value.get("target_node_id")
        if not all(isinstance(item, str) for item in (schema, raw_type, source, target)):
            raise EvidenceTrustGraphError("invalid trust relation identity fields")
        try:
            edge_type = TrustEdgeType(cast(str, raw_type))
        except ValueError as exc:
            raise EvidenceTrustGraphError(f"unknown trust edge type: {raw_type}") from exc
        raw_identity = value.get("relation_identity")
        if not isinstance(raw_identity, Mapping):
            raise EvidenceTrustGraphError("trust relation identity is required")
        return cls(
            edge_type=edge_type,
            source_node_id=cast(str, source),
            target_node_id=cast(str, target),
            relation_identity=ContentAddress.from_dict(
                cast(Mapping[str, object], raw_identity)
            ),
            schema=cast(str, schema),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "edge_type": self.edge_type.value,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "relation_identity": self.relation_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.relation_identity != ContentAddress.for_value(self.canonical_body()):
            raise EvidenceTrustGraphError("trust relation content-address mismatch")


@dataclass(frozen=True, slots=True)
class TrustNode:
    node_id: str
    kind: TrustNodeKind
    source_identity: ContentAddress
    attributes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _identifier(self.node_id, field_name="trust node_id")
        keys = [key for key, _value in self.attributes]
        if len(keys) != len(set(keys)):
            raise EvidenceTrustGraphError("trust node attributes must have unique keys")
        if any(not key or not value for key, value in self.attributes):
            raise EvidenceTrustGraphError("trust node attributes cannot be blank")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "source_identity": self.source_identity.canonical_dict(),
            "attributes": {key: value for key, value in self.attributes},
        }


@dataclass(frozen=True, slots=True)
class TrustEdge:
    edge_type: TrustEdgeType
    source_node_id: str
    target_node_id: str
    basis_event_id: ContentAddress
    edge_identity: ContentAddress

    @classmethod
    def build(
        cls,
        *,
        edge_type: TrustEdgeType,
        source_node_id: str,
        target_node_id: str,
        basis_event_id: ContentAddress,
    ) -> TrustEdge:
        if source_node_id == target_node_id:
            raise EvidenceTrustGraphError("trust edge self-loop is forbidden")
        body = {
            "edge_type": edge_type.value,
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "basis_event_id": basis_event_id.canonical_dict(),
        }
        return cls(
            edge_type=edge_type,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            basis_event_id=basis_event_id,
            edge_identity=ContentAddress.for_value(body),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "edge_type": self.edge_type.value,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "basis_event_id": self.basis_event_id.canonical_dict(),
            "edge_identity": self.edge_identity.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceTrustGraph:
    case_id: CaseId
    ledger_head: ContentAddress | None
    epistemic_projection_identity: ContentAddress
    trust_policy_identity: ContentAddress
    nodes: tuple[TrustNode, ...]
    edges: tuple[TrustEdge, ...]
    graph_identity: ContentAddress
    schema: str = TRUST_GRAPH_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        events: tuple[LedgerEvent, ...],
        epistemic_projection: EpistemicProjectionV2,
        policy: TrustPolicyV1,
    ) -> EvidenceTrustGraph:
        policy.verify()
        epistemic_projection.verify()
        ledger_head = events[-1].event_id if events else None
        if epistemic_projection.case_id != case_id:
            raise EvidenceTrustGraphError("epistemic projection belongs to another case")
        if epistemic_projection.ledger_head != ledger_head:
            raise EvidenceTrustGraphError("epistemic projection ledger head is stale")

        nodes: dict[str, TrustNode] = {}
        edges: list[TrustEdge] = []
        semantic_edges: set[tuple[str, str, str]] = set()

        def add_node(node: TrustNode) -> None:
            existing = nodes.get(node.node_id)
            if existing is not None and existing != node:
                raise EvidenceTrustGraphError("trust node identity collision")
            if existing is None:
                if len(nodes) >= policy.max_nodes:
                    raise EvidenceTrustGraphError("TRUST_GRAPH_NODE_LIMIT_EXCEEDED")
                nodes[node.node_id] = node

        def add_edge(edge: TrustEdge) -> None:
            if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
                raise EvidenceTrustGraphError("trust edge references an unknown node")
            semantic_key = (
                edge.edge_type.value,
                edge.source_node_id,
                edge.target_node_id,
            )
            if semantic_key in semantic_edges:
                raise EvidenceTrustGraphError("duplicate semantic trust edge")
            if len(edges) >= policy.max_edges:
                raise EvidenceTrustGraphError("TRUST_GRAPH_EDGE_LIMIT_EXCEEDED")
            semantic_edges.add(semantic_key)
            edges.append(edge)

        for event in events:
            if event.case_id != case_id:
                raise EvidenceTrustGraphError("trust graph received a foreign case event")
            event_id = event_node_id(event.event_id)
            add_node(
                TrustNode(
                    node_id=event_id,
                    kind=TrustNodeKind.EVENT,
                    source_identity=event.event_id,
                    attributes=(("event_type", event.event_type),),
                )
            )

            if event.event_type == ASSERTION_CREATED_EVENT_V1:
                raw = event.payload.get("assertion")
                if not isinstance(raw, Mapping):
                    raise EvidenceTrustGraphError("assertion trust payload is invalid")
                assertion = Assertion.from_dict(cast(Mapping[str, object], raw))
                node_id = assertion_node_id(assertion.assertion_id)
                add_node(
                    TrustNode(
                        node_id=node_id,
                        kind=TrustNodeKind.ASSERTION,
                        source_identity=assertion.assertion_id,
                        attributes=(
                            ("assertion_type", assertion.assertion_type),
                            ("initial_status", assertion.initial_status.value),
                        ),
                    )
                )
                add_edge(
                    TrustEdge.build(
                        edge_type=TrustEdgeType.RECORDED_BY,
                        source_node_id=node_id,
                        target_node_id=event_id,
                        basis_event_id=event.event_id,
                    )
                )
                for evidence_ref in assertion.evidence_refs:
                    if evidence_ref.case_id != case_id:
                        raise EvidenceTrustGraphError("cross-case trust edge is forbidden")
                    add_edge(
                        TrustEdge.build(
                            edge_type=TrustEdgeType.SUPPORTS,
                            source_node_id=event_node_id(evidence_ref.event_id),
                            target_node_id=node_id,
                            basis_event_id=event.event_id,
                        )
                    )

            elif event.event_type == ASSERTION_TRANSITION_EVENT_V1:
                raw = event.payload.get("decision")
                if not isinstance(raw, Mapping):
                    raise EvidenceTrustGraphError("transition trust payload is invalid")
                decision = EpistemicDecisionV2.from_dict(cast(Mapping[str, object], raw))
                node_id = decision_node_id(decision.decision_id)
                add_node(
                    TrustNode(
                        node_id=node_id,
                        kind=TrustNodeKind.DECISION,
                        source_identity=decision.decision_id,
                        attributes=(
                            ("source_status", decision.source.value),
                            ("target_status", decision.target.value),
                        ),
                    )
                )
                assertion_id = assertion_node_id(decision.assertion_id)
                add_edge(
                    TrustEdge.build(
                        edge_type=TrustEdgeType.TRANSITIONS,
                        source_node_id=node_id,
                        target_node_id=assertion_id,
                        basis_event_id=event.event_id,
                    )
                )
                add_edge(
                    TrustEdge.build(
                        edge_type=TrustEdgeType.RECORDED_BY,
                        source_node_id=node_id,
                        target_node_id=event_id,
                        basis_event_id=event.event_id,
                    )
                )
                for evidence_ref in decision.evidence_refs:
                    if evidence_ref.case_id != case_id:
                        raise EvidenceTrustGraphError("cross-case trust edge is forbidden")
                    add_edge(
                        TrustEdge.build(
                            edge_type=TrustEdgeType.SUPPORTS,
                            source_node_id=event_node_id(evidence_ref.event_id),
                            target_node_id=node_id,
                            basis_event_id=event.event_id,
                        )
                    )

            elif event.event_type == TRUST_RELATION_EVENT_V1:
                raw = event.payload.get("relation")
                if not isinstance(raw, Mapping):
                    raise EvidenceTrustGraphError("trust relation payload is invalid")
                relation = TrustRelationDeclaration.from_dict(
                    cast(Mapping[str, object], raw)
                )
                if relation.edge_type not in policy.allowed_explicit_edges:
                    raise EvidenceTrustGraphError("trust relation edge type denied by policy")
                add_edge(
                    TrustEdge.build(
                        edge_type=relation.edge_type,
                        source_node_id=relation.source_node_id,
                        target_node_id=relation.target_node_id,
                        basis_event_id=event.event_id,
                    )
                )

            elif event.event_type.startswith("trust."):
                raise EvidenceTrustGraphError(
                    f"unknown trust event type: {event.event_type}"
                )

        ordered_nodes = tuple(sorted(nodes.values(), key=lambda item: item.node_id))
        ordered_edges = tuple(
            sorted(
                edges,
                key=lambda item: (
                    item.edge_type.value,
                    item.source_node_id,
                    item.target_node_id,
                    str(item.basis_event_id),
                ),
            )
        )
        body = {
            "schema": TRUST_GRAPH_SCHEMA_V1,
            "case_id": case_id.value,
            "ledger_head": ledger_head.canonical_dict() if ledger_head else None,
            "epistemic_projection_identity": (
                epistemic_projection.projection_identity.canonical_dict()
            ),
            "trust_policy_identity": policy.policy_identity.canonical_dict(),
            "nodes": [node.canonical_dict() for node in ordered_nodes],
            "edges": [edge.canonical_dict() for edge in ordered_edges],
        }
        return cls(
            case_id=case_id,
            ledger_head=ledger_head,
            epistemic_projection_identity=epistemic_projection.projection_identity,
            trust_policy_identity=policy.policy_identity,
            nodes=ordered_nodes,
            edges=ordered_edges,
            graph_identity=ContentAddress.for_value(body),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id.value,
            "ledger_head": self.ledger_head.canonical_dict() if self.ledger_head else None,
            "epistemic_projection_identity": (
                self.epistemic_projection_identity.canonical_dict()
            ),
            "trust_policy_identity": self.trust_policy_identity.canonical_dict(),
            "nodes": [node.canonical_dict() for node in self.nodes],
            "edges": [edge.canonical_dict() for edge in self.edges],
        }

    def verify(self) -> None:
        if self.graph_identity != ContentAddress.for_value(self.canonical_body()):
            raise EvidenceTrustGraphError("trust graph identity mismatch")

    def node(self, node_id: str) -> TrustNode | None:
        return next((node for node in self.nodes if node.node_id == node_id), None)
