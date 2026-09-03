from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agents.contract import (
    AgentArtifact,
    AgentContract,
    AgentRequest,
    AgentResourceLimits,
    ProvenanceRef,
)
from agents.registry import AgentRegistry
from agents.runner import AgentRunner, AgentRunStatus
from core.models.ids import AgentId
from knowledge.provenance import EpistemicStatus

AGENT_ID = AgentId(UUID("22222222-2222-4222-8222-222222222222"))


def contract() -> AgentContract:
    return AgentContract(
        agent_id=AGENT_ID,
        name="RunnerTestAgent",
        version="1.0.0",
        input_schema="document.v1",
        output_schema="facts.v1",
        required_evidence_types=("document_text",),
        allowed_operations=("read_evidence", "emit_artifact"),
        forbidden_operations=("persist_case",),
        allowed_epistemic_statuses=(EpistemicStatus.EXTRACTED,),
        validation_gates=("contract", "provenance"),
        resource_limits=AgentResourceLimits(max_runtime_seconds=1.0),
    )


@dataclass
class StubAgent:
    artifact: AgentArtifact

    @property
    def contract(self) -> AgentContract:
        return contract()

    def execute(self, request: AgentRequest) -> AgentArtifact:
        return self.artifact


def valid_artifact() -> AgentArtifact:
    return AgentArtifact(
        agent_id=AGENT_ID,
        agent_version="1.0.0",
        artifact_type="facts.v1",
        payload=("fact",),
        provenance=(
            ProvenanceRef(
                source_document_id="doc-1",
                source_document_sha256="a" * 64,
                page=1,
                char_start=0,
                char_end=4,
            ),
        ),
        epistemic_statuses=(EpistemicStatus.EXTRACTED,),
    )


def make_runner(artifact: AgentArtifact) -> AgentRunner:
    registry = AgentRegistry()
    registry.register(StubAgent(artifact))
    return AgentRunner(registry)


def test_runner_rejects_missing_required_evidence_before_execution() -> None:
    runner = make_runner(valid_artifact())
    result = runner.run(
        AGENT_ID,
        "1.0.0",
        AgentRequest(schema="document.v1", payload={}, evidence_types=frozenset()),
    )

    assert result.status is AgentRunStatus.FAIL
    assert result.artifact is None
    assert "missing required evidence types" in result.errors[0]


def test_runner_rejects_non_empty_artifact_without_provenance() -> None:
    artifact = AgentArtifact(
        agent_id=AGENT_ID,
        agent_version="1.0.0",
        artifact_type="facts.v1",
        payload=("fact",),
        epistemic_statuses=(EpistemicStatus.EXTRACTED,),
    )
    runner = make_runner(artifact)
    result = runner.run(
        AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="document.v1",
            payload={"text": "x"},
            evidence_types=frozenset({"document_text"}),
        ),
    )

    assert result.status is AgentRunStatus.FAIL
    assert "requires provenance" in result.errors[0]


def test_runner_rejects_epistemic_status_outside_contract() -> None:
    base = valid_artifact()
    artifact = AgentArtifact(
        agent_id=base.agent_id,
        agent_version=base.agent_version,
        artifact_type=base.artifact_type,
        payload=base.payload,
        provenance=base.provenance,
        epistemic_statuses=(EpistemicStatus.INFERRED,),
    )
    runner = make_runner(artifact)
    result = runner.run(
        AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="document.v1",
            payload={"text": "x"},
            evidence_types=frozenset({"document_text"}),
        ),
    )

    assert result.status is AgentRunStatus.FAIL
    assert "outside contract" in result.errors[0]


def test_runner_accepts_contract_compliant_artifact() -> None:
    runner = make_runner(valid_artifact())
    result = runner.run(
        AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="document.v1",
            payload={"text": "x"},
            evidence_types=frozenset({"document_text"}),
        ),
    )

    assert result.status is AgentRunStatus.PASS
    assert result.accepted is True
    assert result.errors == ()
