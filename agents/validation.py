"""Fail-closed validation boundary for controlled agent execution."""

from __future__ import annotations

from collections.abc import Collection

from agents.contract import AgentArtifact, AgentContract, AgentRequest


class AgentValidationGate:
    """Validate inputs and outputs without mutating Case or agent state."""

    def validate_request(self, contract: AgentContract, request: AgentRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if request.schema != contract.input_schema:
            errors.append(
                f"input schema mismatch: expected {contract.input_schema!r}, got {request.schema!r}"
            )
        missing = set(contract.required_evidence_types) - set(request.evidence_types)
        if missing:
            errors.append(f"missing required evidence types: {sorted(missing)}")
        return tuple(errors)

    def validate_artifact(
        self,
        contract: AgentContract,
        artifact: AgentArtifact,
        *,
        runtime_seconds: float,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if artifact.agent_id != contract.agent_id:
            errors.append("artifact agent_id does not match contract")
        if artifact.agent_version != contract.version:
            errors.append("artifact agent_version does not match contract")
        if artifact.artifact_type != contract.output_schema:
            errors.append(
                f"output schema mismatch: expected {contract.output_schema!r}, "
                f"got {artifact.artifact_type!r}"
            )

        illegal_statuses = set(artifact.epistemic_statuses) - set(
            contract.allowed_epistemic_statuses
        )
        if illegal_statuses:
            errors.append(
                "artifact contains epistemic statuses outside contract: "
                + repr(sorted(status.value for status in illegal_statuses))
            )

        if contract.provenance_required and self._has_items(artifact.payload) and not artifact.provenance:
            errors.append("non-empty artifact requires provenance")

        if runtime_seconds > contract.resource_limits.max_runtime_seconds:
            errors.append("agent exceeded max_runtime_seconds")

        model_calls = self._non_negative_number(artifact.metadata.get("model_calls", 0), "model_calls", errors)
        cost_units = self._non_negative_number(artifact.metadata.get("cost_units", 0.0), "cost_units", errors)
        if model_calls is not None and model_calls > contract.resource_limits.max_model_calls:
            errors.append("agent exceeded max_model_calls")
        if cost_units is not None and cost_units > contract.resource_limits.max_cost_units:
            errors.append("agent exceeded max_cost_units")

        return tuple(errors)

    @staticmethod
    def _has_items(payload: object) -> bool:
        if payload is None:
            return False
        if isinstance(payload, Collection):
            return len(payload) > 0
        return True

    @staticmethod
    def _non_negative_number(value: object, name: str, errors: list[str]) -> float | None:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"artifact metadata {name} must be a non-negative number")
            return None
        return float(value)
