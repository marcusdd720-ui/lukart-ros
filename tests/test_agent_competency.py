from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from agents.competency import AgentCompetencyProfile, AgentCompetencyRegistry
from core.models.ids import AgentId

AGENT_ID = AgentId(UUID("77777777-7777-4777-8777-777777777777"))


def profile() -> AgentCompetencyProfile:
    return AgentCompetencyProfile(
        agent_id=AGENT_ID,
        agent_version="1.0.0",
        capabilities=("review.dossier",),
        input_schemas=("dossier-review.v1",),
        output_schemas=("review-findings.v1",),
    )


def test_competency_profile_is_immutable_and_version_bound() -> None:
    item = profile()

    with pytest.raises(FrozenInstanceError):
        item.agent_version = "2.0.0"  # type: ignore[misc]


def test_competency_profile_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        AgentCompetencyProfile(
            agent_id=AGENT_ID,
            agent_version="1.0.0",
            capabilities=("review.dossier", "review.dossier"),
            input_schemas=("dossier-review.v1",),
            output_schemas=("review-findings.v1",),
        )


def test_support_requires_capability_and_schema_match() -> None:
    item = profile()

    assert item.supports(
        "review.dossier",
        input_schema="dossier-review.v1",
        output_schema="review-findings.v1",
    )
    assert not item.supports("extract.facts")
    assert not item.supports("review.dossier", input_schema="claims.v1")


def test_registry_is_exact_version_and_deterministic() -> None:
    registry = AgentCompetencyRegistry()
    registry.register(profile())

    assert registry.get(AGENT_ID, "1.0.0") == profile()
    assert registry.matching("review.dossier") == (profile(),)
    with pytest.raises(KeyError):
        registry.get(AGENT_ID, "2.0.0")
