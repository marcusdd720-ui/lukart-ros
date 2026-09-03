"""Immutable capability declarations for controlled agents.

A competency profile describes what an agent is designed to do. It is not a
quality certificate and must never be interpreted as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.models.ids import AgentId

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True, slots=True)
class AgentCompetencyProfile:
    agent_id: AgentId
    agent_version: str
    capabilities: tuple[str, ...]
    input_schemas: tuple[str, ...]
    output_schemas: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SEMVER_RE.fullmatch(self.agent_version):
            raise ValueError("agent_version must use MAJOR.MINOR.PATCH semver")
        self._require_non_empty_unique("capabilities", self.capabilities)
        self._require_non_empty_unique("input_schemas", self.input_schemas)
        self._require_non_empty_unique("output_schemas", self.output_schemas)

    def supports(
        self,
        capability: str,
        *,
        input_schema: str | None = None,
        output_schema: str | None = None,
    ) -> bool:
        if capability not in self.capabilities:
            return False
        if input_schema is not None and input_schema not in self.input_schemas:
            return False
        return output_schema is None or output_schema in self.output_schemas

    @staticmethod
    def _require_non_empty_unique(name: str, values: tuple[str, ...]) -> None:
        if not values or any(not value.strip() for value in values):
            raise ValueError(f"{name} must contain non-empty values")
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must not contain duplicates")


class AgentCompetencyRegistry:
    """Registry of declarations keyed by exact agent id and version."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[AgentId, str], AgentCompetencyProfile] = {}

    def register(self, profile: AgentCompetencyProfile) -> None:
        key = (profile.agent_id, profile.agent_version)
        if key in self._profiles:
            raise ValueError("competency profile already registered for agent version")
        self._profiles[key] = profile

    def get(self, agent_id: AgentId, agent_version: str) -> AgentCompetencyProfile:
        key = (agent_id, agent_version)
        try:
            return self._profiles[key]
        except KeyError as exc:
            raise KeyError(f"competency profile not found for {agent_id}@{agent_version}") from exc

    def matching(
        self,
        capability: str,
        *,
        input_schema: str | None = None,
        output_schema: str | None = None,
    ) -> tuple[AgentCompetencyProfile, ...]:
        matches = (
            profile
            for profile in self._profiles.values()
            if profile.supports(
                capability,
                input_schema=input_schema,
                output_schema=output_schema,
            )
        )
        return tuple(sorted(matches, key=lambda item: (str(item.agent_id), item.agent_version)))
