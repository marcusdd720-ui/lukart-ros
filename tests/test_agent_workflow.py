from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agents.contract import AgentArtifact, AgentContract, AgentRequest, AgentResourceLimits
from agents.registry import AgentRegistry
from agents.runner import AgentRunner
from agents.workflow import AgentWorkflowExecutor, AgentWorkflowStep
from core.models.ids import AgentId
from knowledge.provenance import EpistemicStatus

FIRST_ID = AgentId(UUID("33333333-3333-4333-8333-333333333333"))
SECOND_ID = AgentId(UUID("44444444-4444-4444-8444-444444444444"))


def make_contract(agent_id: AgentId, name: str) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        name=name,
        version="1.0.0",
        input_schema="workflow.v1",
        output_schema="workflow-result.v1",
        required_evidence_types=(),
        allowed_operations=("emit_artifact",),
        forbidden_operations=("persist_case",),
        allowed_epistemic_statuses=(EpistemicStatus.EXTRACTED,),
        validation_gates=("contract",),
        resource_limits=AgentResourceLimits(max_runtime_seconds=1.0),
        provenance_required=False,
    )


@dataclass
class CountingAgent:
    _contract: AgentContract
    calls: int = 0
    valid: bool = True

    @property
    def contract(self) -> AgentContract:
        return self._contract

    def execute(self, request: AgentRequest) -> AgentArtifact:
        self.calls += 1
        artifact_type = self.contract.output_schema if self.valid else "wrong-schema.v1"
        return AgentArtifact(
            agent_id=self.contract.agent_id,
            agent_version=self.contract.version,
            artifact_type=artifact_type,
            payload=(),
            epistemic_statuses=(EpistemicStatus.EXTRACTED,),
        )


def test_workflow_executes_registered_steps_in_order() -> None:
    first = CountingAgent(make_contract(FIRST_ID, "First"))
    second = CountingAgent(make_contract(SECOND_ID, "Second"))
    registry = AgentRegistry()
    registry.register(first)
    registry.register(second)

    executor = AgentWorkflowExecutor(AgentRunner(registry))
    request = AgentRequest(schema="workflow.v1", payload={})
    result = executor.execute(
        (
            AgentWorkflowStep("first", FIRST_ID, "1.0.0", request),
            AgentWorkflowStep("second", SECOND_ID, "1.0.0", request),
        )
    )

    assert result.completed is True
    assert result.failed_step is None
    assert len(result.steps) == 2
    assert first.calls == 1
    assert second.calls == 1


def test_workflow_stops_after_first_failed_validation_gate() -> None:
    first = CountingAgent(make_contract(FIRST_ID, "First"), valid=False)
    second = CountingAgent(make_contract(SECOND_ID, "Second"))
    registry = AgentRegistry()
    registry.register(first)
    registry.register(second)

    executor = AgentWorkflowExecutor(AgentRunner(registry))
    request = AgentRequest(schema="workflow.v1", payload={})
    result = executor.execute(
        (
            AgentWorkflowStep("first", FIRST_ID, "1.0.0", request),
            AgentWorkflowStep("second", SECOND_ID, "1.0.0", request),
        )
    )

    assert result.completed is False
    assert result.failed_step == "first"
    assert len(result.steps) == 1
    assert first.calls == 1
    assert second.calls == 0
