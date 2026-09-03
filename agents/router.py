"""Deterministic routing across registered, profiled and certified agents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agents.certification import AgentCertificationStatus
from agents.competency import AgentCompetencyProfile, AgentCompetencyRegistry
from agents.registry import AgentRegistry
from core.models.ids import AgentId


class AgentRoutingError(LookupError):
    """Raised when routing cannot produce one authorized agent."""


@dataclass(frozen=True, slots=True)
class AgentRouteRequest:
    capability: str
    input_schema: str
    output_schema: str
    allowed_certification_statuses: tuple[AgentCertificationStatus, ...] = (
        AgentCertificationStatus.CERTIFIED,
    )

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise ValueError("capability is required")
        if not self.input_schema.strip() or not self.output_schema.strip():
            raise ValueError("input_schema and output_schema are required")
        if not self.allowed_certification_statuses:
            raise ValueError("at least one certification status must be allowed")


@dataclass(frozen=True, slots=True)
class AgentRoute:
    agent_id: AgentId
    agent_version: str
    capability: str
    certification_status: AgentCertificationStatus


class CapabilityRouter:
    """Select exactly one authorized agent or fail closed.

    Competency declarations and certification state are intentionally separate.
    A declared capability never implies analytical approval.
    """

    def __init__(
        self,
        agents: AgentRegistry,
        competencies: AgentCompetencyRegistry,
        certifications: Mapping[tuple[str, str], AgentCertificationStatus],
    ) -> None:
        self.agents = agents
        self.competencies = competencies
        self.certifications = dict(certifications)

    def route(self, request: AgentRouteRequest) -> AgentRoute:
        profiles = self.competencies.matching(
            request.capability,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
        )
        candidates: list[tuple[AgentCompetencyProfile, AgentCertificationStatus]] = []
        for profile in profiles:
            try:
                self.agents.get_contract(profile.agent_id, profile.agent_version)
            except KeyError:
                continue
            status = self.certifications.get((str(profile.agent_id), profile.agent_version))
            if status in request.allowed_certification_statuses:
                candidates.append((profile, status))

        if not candidates:
            raise AgentRoutingError("no authorized agent matches route request")
        if len(candidates) > 1:
            raise AgentRoutingError("ambiguous authorized agent route")

        profile, status = candidates[0]
        return AgentRoute(
            agent_id=profile.agent_id,
            agent_version=profile.agent_version,
            capability=request.capability,
            certification_status=status,
        )
