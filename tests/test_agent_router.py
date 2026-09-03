import pytest

from agents.certification import AgentCertificationStatus
from agents.competency import AgentCompetencyProfile, AgentCompetencyRegistry
from agents.contradiction import CONTRADICTION_AGENT_ID, ContradictionAgent
from agents.registry import AgentRegistry
from agents.reviewer import REVIEWER_AGENT_ID, ReviewerAgent
from agents.router import AgentRouteRequest, AgentRoutingError, CapabilityRouter


def reviewer_profile() -> AgentCompetencyProfile:
    return AgentCompetencyProfile(
        agent_id=REVIEWER_AGENT_ID,
        agent_version="1.0.0",
        capabilities=("review.dossier",),
        input_schemas=("dossier-review.v1",),
        output_schemas=("review-findings.v1",),
    )


def make_router(
    status: AgentCertificationStatus,
) -> CapabilityRouter:
    agents = AgentRegistry()
    agents.register(ReviewerAgent())
    competencies = AgentCompetencyRegistry()
    competencies.register(reviewer_profile())
    return CapabilityRouter(
        agents,
        competencies,
        {(str(REVIEWER_AGENT_ID), "1.0.0"): status},
    )


def request() -> AgentRouteRequest:
    return AgentRouteRequest(
        capability="review.dossier",
        input_schema="dossier-review.v1",
        output_schema="review-findings.v1",
    )


def test_certified_agent_is_selected() -> None:
    route = make_router(AgentCertificationStatus.CERTIFIED).route(request())

    assert route.agent_id == REVIEWER_AGENT_ID
    assert route.agent_version == "1.0.0"
    assert route.certification_status is AgentCertificationStatus.CERTIFIED


def test_declared_but_rejected_agent_is_not_selected_by_default() -> None:
    with pytest.raises(AgentRoutingError, match="no authorized agent"):
        make_router(AgentCertificationStatus.REJECTED).route(request())


def test_nonproduction_route_can_explicitly_allow_evaluated_status() -> None:
    router = make_router(AgentCertificationStatus.EVALUATED)
    route = router.route(
        AgentRouteRequest(
            capability="review.dossier",
            input_schema="dossier-review.v1",
            output_schema="review-findings.v1",
            allowed_certification_statuses=(AgentCertificationStatus.EVALUATED,),
        )
    )

    assert route.certification_status is AgentCertificationStatus.EVALUATED


def test_router_fails_closed_when_profile_has_no_registered_agent() -> None:
    competencies = AgentCompetencyRegistry()
    competencies.register(reviewer_profile())
    router = CapabilityRouter(
        AgentRegistry(),
        competencies,
        {(str(REVIEWER_AGENT_ID), "1.0.0"): AgentCertificationStatus.CERTIFIED},
    )

    with pytest.raises(AgentRoutingError, match="no authorized agent"):
        router.route(request())


def test_router_rejects_ambiguous_authorized_candidates() -> None:
    agents = AgentRegistry()
    agents.register(ReviewerAgent())
    agents.register(ContradictionAgent())
    competencies = AgentCompetencyRegistry()
    competencies.register(reviewer_profile())
    competencies.register(
        AgentCompetencyProfile(
            agent_id=CONTRADICTION_AGENT_ID,
            agent_version="1.0.0",
            capabilities=("review.dossier",),
            input_schemas=("dossier-review.v1",),
            output_schemas=("review-findings.v1",),
        )
    )
    router = CapabilityRouter(
        agents,
        competencies,
        {
            (str(REVIEWER_AGENT_ID), "1.0.0"): AgentCertificationStatus.CERTIFIED,
            (str(CONTRADICTION_AGENT_ID), "1.0.0"): AgentCertificationStatus.CERTIFIED,
        },
    )

    with pytest.raises(AgentRoutingError, match="ambiguous"):
        router.route(request())
