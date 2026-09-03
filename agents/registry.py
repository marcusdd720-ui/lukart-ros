"""Deterministic registry for contract-bound agents."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agents.contract import AgentContract, AgentProtocol
from core.models.ids import AgentId


@dataclass(frozen=True, slots=True)
class AgentRegistration:
    contract: AgentContract
    agent: AgentProtocol


class AgentRegistry:
    """Explicit registry keyed by stable AgentId and semantic version."""

    def __init__(self) -> None:
        self._items: dict[tuple[UUID, str], AgentRegistration] = {}

    @staticmethod
    def _key(agent_id: AgentId, version: str) -> tuple[UUID, str]:
        return (UUID(str(agent_id)), version)

    def register(self, agent: AgentProtocol) -> None:
        contract = agent.contract
        key = self._key(contract.agent_id, contract.version)
        if key in self._items:
            raise ValueError(
                f"agent already registered: {contract.name} {contract.version}"
            )
        self._items[key] = AgentRegistration(contract=contract, agent=agent)

    def get(self, agent_id: AgentId, version: str) -> AgentProtocol:
        key = self._key(agent_id, version)
        try:
            return self._items[key].agent
        except KeyError as exc:
            raise KeyError(f"unknown agent/version: {agent_id} {version}") from exc

    def get_contract(self, agent_id: AgentId, version: str) -> AgentContract:
        key = self._key(agent_id, version)
        try:
            return self._items[key].contract
        except KeyError as exc:
            raise KeyError(f"unknown agent/version: {agent_id} {version}") from exc

    def registrations(self) -> tuple[AgentRegistration, ...]:
        return tuple(
            self._items[key]
            for key in sorted(self._items, key=lambda item: (str(item[0]), item[1]))
        )
