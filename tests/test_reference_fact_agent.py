from __future__ import annotations

from agents.contract import AgentRequest
from agents.reference_fact import REFERENCE_FACT_AGENT_ID, ReferenceFactAgent
from agents.registry import AgentRegistry
from agents.runner import AgentRunner, AgentRunStatus
from knowledge.provenance import EntityType, EpistemicStatus, ExtractedFact


def test_reference_fact_agent_runs_through_controlled_runtime() -> None:
    registry = AgentRegistry()
    registry.register(ReferenceFactAgent())
    runner = AgentRunner(registry)

    result = runner.run(
        REFERENCE_FACT_AGENT_ID,
        "1.0.0",
        AgentRequest(
            schema="lukart.document_text.v1",
            payload={
                "document_id": "synthetic-doc-1",
                "document_type": "pismo_procesowe",
                "text": "Sygn. akt III RC 956/25. Kwota 800,00 zł. art. 135 § 1.",
            },
            evidence_types=frozenset({"document_text"}),
        ),
    )

    assert result.status is AgentRunStatus.PASS
    assert result.artifact is not None
    facts = result.artifact.payload
    assert isinstance(facts, tuple)
    assert all(isinstance(fact, ExtractedFact) for fact in facts)
    assert {fact.entity_type for fact in facts} >= {
        EntityType.CASE_NUMBER,
        EntityType.AMOUNT,
        EntityType.LEGAL_BASIS,
    }
    assert result.artifact.epistemic_statuses == (EpistemicStatus.EXTRACTED,)
    assert len(result.artifact.provenance) == len(facts)
    assert all(ref.source_document_sha256 for ref in result.artifact.provenance)
    assert result.artifact.metadata["model_calls"] == 0
    assert result.artifact.metadata["cost_units"] == 0.0
