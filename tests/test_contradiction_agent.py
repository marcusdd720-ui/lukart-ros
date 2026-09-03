from agents.contradiction import CONTRADICTION_AGENT_ID, ContradictionAgent
from agents.contract import AgentRequest
from agents.registry import AgentRegistry
from agents.runner import AgentRunner, AgentRunStatus
from knowledge.provenance import EpistemicStatus


def test_contradiction_agent_preserves_both_sides_and_marks_unresolved() -> None:
    agent = ContradictionAgent()
    registry = AgentRegistry()
    registry.register(agent)
    runner = AgentRunner(registry)

    result = runner.run(
        CONTRADICTION_AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="claims.v1",
            payload={
                "claims": (
                    {
                        "subject": "person",
                        "predicate": "status",
                        "value": "active",
                        "source_document_id": "doc-a",
                    },
                    {
                        "subject": "person",
                        "predicate": "status",
                        "value": "inactive",
                        "source_document_id": "doc-b",
                    },
                )
            },
        ),
    )

    assert result.status is AgentRunStatus.PASS
    assert result.artifact is not None
    assert result.artifact.epistemic_statuses == (EpistemicStatus.DISPUTED,)
    assert result.artifact.payload == (
        {
            "subject": "person",
            "predicate": "status",
            "left_value": "active",
            "right_value": "inactive",
            "left_source_document_id": "doc-a",
            "right_source_document_id": "doc-b",
            "resolution_status": "UNRESOLVED",
        },
    )


def test_contradiction_agent_does_not_invent_resolution() -> None:
    agent = ContradictionAgent()
    artifact = agent.execute(
        AgentRequest(
            schema="claims.v1",
            payload={
                "claims": (
                    {"subject": "x", "predicate": "p", "value": "one"},
                    {"subject": "x", "predicate": "p", "value": "two"},
                )
            },
        )
    )

    finding = artifact.payload[0]
    assert finding["resolution_status"] == "UNRESOLVED"
    assert "winner" not in finding


def test_contradiction_agent_returns_empty_clean_result() -> None:
    agent = ContradictionAgent()
    artifact = agent.execute(
        AgentRequest(
            schema="claims.v1",
            payload={"claims": ({"subject": "x", "predicate": "p", "value": "one"},)},
        )
    )

    assert artifact.payload == ()
    assert artifact.epistemic_statuses == ()
