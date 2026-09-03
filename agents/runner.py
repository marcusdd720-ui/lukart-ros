"""Controlled execution runtime for contract-bound agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic

from agents.contract import AgentArtifact, AgentRequest
from agents.registry import AgentRegistry
from agents.validation import AgentValidationGate
from core.models.ids import AgentId


class AgentRunStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    status: AgentRunStatus
    agent_id: AgentId
    agent_version: str
    runtime_seconds: float
    artifact: AgentArtifact | None = None
    errors: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status is AgentRunStatus.PASS and self.artifact is not None


class AgentRunner:
    """Run registered agents through pre/post validation gates.

    The runner deliberately has no Case persistence API. An accepted artifact may be
    handed to a separate persistence boundary only after this result is PASS.
    """

    def __init__(self, registry: AgentRegistry, gate: AgentValidationGate | None = None) -> None:
        self.registry = registry
        self.gate = gate or AgentValidationGate()

    def run(self, agent_id: AgentId, version: str, request: AgentRequest) -> AgentRunResult:
        agent = self.registry.get(agent_id, version)
        contract = agent.contract

        request_errors = self.gate.validate_request(contract, request)
        if request_errors:
            return AgentRunResult(
                status=AgentRunStatus.FAIL,
                agent_id=contract.agent_id,
                agent_version=contract.version,
                runtime_seconds=0.0,
                errors=request_errors,
            )

        started = monotonic()
        try:
            artifact = agent.execute(request)
        except Exception as exc:  # noqa: BLE001 - boundary must convert agent failure to result
            runtime = monotonic() - started
            return AgentRunResult(
                status=AgentRunStatus.FAIL,
                agent_id=contract.agent_id,
                agent_version=contract.version,
                runtime_seconds=runtime,
                errors=(f"agent execution failed: {type(exc).__name__}: {exc}",),
            )

        runtime = monotonic() - started
        artifact_errors = self.gate.validate_artifact(
            contract,
            artifact,
            runtime_seconds=runtime,
        )
        if artifact_errors:
            return AgentRunResult(
                status=AgentRunStatus.FAIL,
                agent_id=contract.agent_id,
                agent_version=contract.version,
                runtime_seconds=runtime,
                artifact=artifact,
                errors=artifact_errors,
            )

        return AgentRunResult(
            status=AgentRunStatus.PASS,
            agent_id=contract.agent_id,
            agent_version=contract.version,
            runtime_seconds=runtime,
            artifact=artifact,
        )
