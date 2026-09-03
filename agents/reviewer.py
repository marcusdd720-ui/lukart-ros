"""Controlled reviewer agent backed by the canonical deterministic dossier checklist."""

from __future__ import annotations

from uuid import UUID

from agents.contract import AgentArtifact, AgentContract, AgentRequest, AgentResourceLimits
from core.models.ids import AgentId
from scripts.review_dossier import review_text

REVIEWER_AGENT_ID = AgentId(UUID("66666666-6666-4666-8666-666666666666"))


class ReviewerAgent:
    """Review a dossier and emit findings without mutating or approving it."""

    @property
    def contract(self) -> AgentContract:
        return AgentContract(
            agent_id=REVIEWER_AGENT_ID,
            name="ReviewerAgent",
            version="1.0.0",
            input_schema="dossier-review.v1",
            output_schema="review-findings.v1",
            required_evidence_types=(),
            allowed_operations=("read_dossier", "emit_findings"),
            forbidden_operations=(
                "modify_dossier",
                "persist_case",
                "promote_epistemic_status",
                "approve_unsupported_conclusion",
            ),
            allowed_epistemic_statuses=(),
            validation_gates=("contract", "review-only"),
            resource_limits=AgentResourceLimits(max_runtime_seconds=1.0),
            provenance_required=False,
            deterministic=True,
        )

    def execute(self, request: AgentRequest) -> AgentArtifact:
        text = request.payload.get("text")
        signature_hint = request.payload.get("signature_hint", "DS.3960")
        if not isinstance(text, str):
            raise ValueError("dossier review text must be a string")
        if not isinstance(signature_hint, str):
            raise ValueError("signature_hint must be a string")

        findings = review_text(text, signature_hint=signature_hint)
        payload = tuple(
            {
                "severity": finding.severity,
                "code": finding.code,
                "message": finding.message,
            }
            for finding in findings
        )
        return AgentArtifact(
            agent_id=self.contract.agent_id,
            agent_version=self.contract.version,
            artifact_type=self.contract.output_schema,
            payload=payload,
            epistemic_statuses=(),
            metadata={
                "model_calls": 0,
                "cost_units": 0.0,
                "error_count": sum(item["severity"] == "ERROR" for item in payload),
                "warning_count": sum(item["severity"] == "WARNING" for item in payload),
            },
        )
