"""Controlled contradiction agent backed by the canonical deterministic detector."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from agents.contract import AgentArtifact, AgentContract, AgentRequest, AgentResourceLimits
from core.models.ids import AgentId
from knowledge.contradiction_detector import FactClaim, detect_contradictions
from knowledge.provenance import EpistemicStatus

CONTRADICTION_AGENT_ID = AgentId(UUID("55555555-5555-4555-8555-555555555555"))


class ContradictionAgent:
    """Detect contradictions without resolving or mutating them."""

    @property
    def contract(self) -> AgentContract:
        return AgentContract(
            agent_id=CONTRADICTION_AGENT_ID,
            name="ContradictionAgent",
            version="1.0.0",
            input_schema="claims.v1",
            output_schema="contradictions.v1",
            required_evidence_types=(),
            allowed_operations=("read_claims", "emit_artifact"),
            forbidden_operations=("resolve_contradiction", "persist_case", "modify_evidence"),
            allowed_epistemic_statuses=(EpistemicStatus.DISPUTED,),
            validation_gates=("contract", "epistemic"),
            resource_limits=AgentResourceLimits(max_runtime_seconds=1.0),
            provenance_required=False,
            deterministic=True,
        )

    def execute(self, request: AgentRequest) -> AgentArtifact:
        claims = self._parse_claims(request.payload.get("claims"))
        findings = detect_contradictions(claims)
        payload = tuple(
            {
                "subject": finding.key[0],
                "predicate": finding.key[1],
                "left_value": finding.left.value,
                "right_value": finding.right.value,
                "left_source_document_id": finding.left.source_document_id,
                "right_source_document_id": finding.right.source_document_id,
                "resolution_status": "UNRESOLVED",
            }
            for finding in findings
        )
        statuses = (EpistemicStatus.DISPUTED,) if payload else ()
        return AgentArtifact(
            agent_id=self.contract.agent_id,
            agent_version=self.contract.version,
            artifact_type=self.contract.output_schema,
            payload=payload,
            epistemic_statuses=statuses,
            metadata={"model_calls": 0, "cost_units": 0.0},
        )

    @staticmethod
    def _parse_claims(raw: object) -> list[FactClaim]:
        if raw is None:
            return []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("claims must be a sequence")

        claims: list[FactClaim] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("each claim must be a mapping")
            subject = item.get("subject")
            predicate = item.get("predicate")
            value = item.get("value")
            source_document_id = item.get("source_document_id", "")
            if not all(isinstance(part, str) for part in (subject, predicate, value)):
                raise ValueError("claim subject, predicate and value must be strings")
            if not isinstance(source_document_id, str):
                raise ValueError("source_document_id must be a string")
            claims.append(
                FactClaim(
                    subject=subject,
                    predicate=predicate,
                    value=value,
                    source_document_id=source_document_id,
                )
            )
        return claims
