from agents.contract import AgentRequest
from agents.registry import AgentRegistry
from agents.reviewer import REVIEWER_AGENT_ID, ReviewerAgent
from agents.runner import AgentRunner, AgentRunStatus


def test_reviewer_agent_runs_through_controlled_runtime() -> None:
    agent = ReviewerAgent()
    registry = AgentRegistry()
    registry.register(agent)

    result = AgentRunner(registry).run(
        REVIEWER_AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="dossier-review.v1",
            payload={"text": "krótki szkic bez wymaganych sekcji", "signature_hint": "ABC/1"},
        ),
    )

    assert result.status is AgentRunStatus.PASS
    assert result.artifact is not None
    assert result.artifact.artifact_type == "review-findings.v1"
    assert result.artifact.epistemic_statuses == ()
    error_count = result.artifact.metadata["error_count"]
    assert isinstance(error_count, int)
    assert error_count > 0


def test_reviewer_contract_is_review_only() -> None:
    contract = ReviewerAgent().contract

    assert "modify_dossier" in contract.forbidden_operations
    assert "persist_case" in contract.forbidden_operations
    assert "promote_epistemic_status" in contract.forbidden_operations
    assert "approve_unsupported_conclusion" in contract.forbidden_operations
    assert contract.allowed_epistemic_statuses == ()


def test_reviewer_emits_findings_without_rewriting_input() -> None:
    agent = ReviewerAgent()
    original = "Stanowisko ABC/1\nI. Fakty\n"
    artifact = agent.execute(
        AgentRequest(
            schema="dossier-review.v1",
            payload={"text": original, "signature_hint": "ABC/1"},
        )
    )

    assert artifact.artifact_type == "review-findings.v1"
    assert artifact.payload != original
    assert "rewritten_text" not in artifact.metadata
