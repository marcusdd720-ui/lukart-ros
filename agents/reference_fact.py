"""Deterministic reference agent used to prove the controlled Agent Layer."""

from __future__ import annotations

from uuid import UUID

from agents.contract import (
    AgentArtifact,
    AgentContract,
    AgentRequest,
    AgentResourceLimits,
    ProvenanceRef,
)
from core.models.ids import AgentId
from knowledge.fact_contract import FactContractValidator
from knowledge.generic_fact_extractor import GenericRegexFactExtractor
from knowledge.provenance import EpistemicStatus, ExtractedFact

REFERENCE_FACT_AGENT_ID = AgentId(UUID("5de4ebc5-09f0-4a7f-9e75-b9f06cb32d01"))


class ReferenceFactAgent:
    """High-precision deterministic fact extractor behind an Agent Step Contract."""

    def __init__(self) -> None:
        self.extractor = GenericRegexFactExtractor()
        self.fact_validator = FactContractValidator()
        self._contract = AgentContract(
            agent_id=REFERENCE_FACT_AGENT_ID,
            name="ReferenceFactAgent",
            version="1.0.0",
            input_schema="lukart.document_text.v1",
            output_schema="lukart.extracted_facts.v1",
            required_evidence_types=("document_text",),
            allowed_operations=("read_evidence", "extract_facts", "emit_artifact"),
            forbidden_operations=("persist_case", "promote_epistemic_status", "network_access"),
            allowed_epistemic_statuses=(EpistemicStatus.EXTRACTED,),
            validation_gates=("agent_envelope", "fact_contract", "provenance"),
            resource_limits=AgentResourceLimits(
                max_runtime_seconds=2.0,
                max_model_calls=0,
                max_cost_units=0.0,
            ),
            provenance_required=True,
            deterministic=True,
        )

    @property
    def contract(self) -> AgentContract:
        return self._contract

    def execute(self, request: AgentRequest) -> AgentArtifact:
        document_id = self._required_string(request, "document_id")
        document_type = self._required_string(request, "document_type")
        text = self._required_string(request, "text", allow_empty=True)
        facts = tuple(self.extractor(document_id, document_type, text))
        self.fact_validator.validate_or_raise(facts)

        return AgentArtifact(
            agent_id=self.contract.agent_id,
            agent_version=self.contract.version,
            artifact_type=self.contract.output_schema,
            payload=facts,
            provenance=tuple(self._provenance(fact) for fact in facts),
            epistemic_statuses=(EpistemicStatus.EXTRACTED,) if facts else (),
            metadata={
                "model_calls": 0,
                "cost_units": 0.0,
                "extractor_version": self.extractor.version,
                "fact_count": len(facts),
            },
        )

    @staticmethod
    def _required_string(
        request: AgentRequest,
        key: str,
        *,
        allow_empty: bool = False,
    ) -> str:
        value = request.payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"request payload {key!r} must be a string")
        if not allow_empty and not value.strip():
            raise ValueError(f"request payload {key!r} must not be empty")
        return value

    @staticmethod
    def _provenance(fact: ExtractedFact) -> ProvenanceRef:
        return ProvenanceRef(
            source_document_id=fact.source_document_id,
            source_document_sha256=fact.source_document_sha256,
            page=fact.page,
            char_start=fact.char_start,
            char_end=fact.char_end,
        )
