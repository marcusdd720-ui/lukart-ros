from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from agents.contract import (
    AgentArtifact,
    AgentContract,
    AgentRequest,
    AgentResourceLimits,
)
from agents.registry import AgentRegistry
from core.models.ids import AgentId
from knowledge.provenance import EpistemicStatus

AGENT_ID = AgentId(UUID("11111111-1111-4111-8111-111111111111"))


def make_contract(**overrides: object) -> AgentContract:
    values: dict[str, object] = {
        "agent_id": AGENT_ID,
        "name": "Reference",
        "version": "1.0.0",
        "input_schema": "test.input.v1",
        "output_schema": "test.output.v1",
        "required_evidence_types": ("document_text",),
        "allowed_operations": ("read_evidence", "emit_artifact"),
        "forbidden_operations": ("persist_case",),
        "allowed_epistemic_statuses": (EpistemicStatus.EXTRACTED,),
        "validation_gates": ("contract", "provenance"),
        "resource_limits": AgentResourceLimits(max_runtime_seconds=1.0),
    }
    values.update(overrides)
    return AgentContract(**values)  # type: ignore[arg-type]


@dataclass
class StubAgent:
    contract: AgentContract

    def execute(self, request: AgentRequest) -> AgentArtifact:
        return AgentArtifact(
            agent_id=self.contract.agent_id,
            agent_version=self.contract.version,
            artifact_type=self.contract.output_schema,
            payload=request.payload,
            epistemic_statuses=(EpistemicStatus.EXTRACTED,),
        )


def test_contract_rejects_non_semver_version() -> None:
    with pytest.raises(ValueError, match="semver"):
        make_contract(version="v1")


def test_contract_rejects_operation_overlap() -> None:
    with pytest.raises(ValueError, match="both allowed and forbidden"):
        make_contract(
            allowed_operations=("persist_case",),
            forbidden_operations=("persist_case",),
        )


def test_registry_rejects_duplicate_agent_version() -> None:
    registry = AgentRegistry()
    agent = StubAgent(make_contract())
    registry.register(agent)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(agent)


def test_registry_uses_exact_agent_version() -> None:
    registry = AgentRegistry()
    v1 = StubAgent(make_contract(version="1.0.0"))
    v2 = StubAgent(make_contract(version="1.1.0"))
    registry.register(v2)
    registry.register(v1)

    assert registry.get(AGENT_ID, "1.0.0") is v1
    assert [item.contract.version for item in registry.registrations()] == ["1.0.0", "1.1.0"]
