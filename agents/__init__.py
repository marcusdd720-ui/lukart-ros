"""Controlled Agent Layer for LukArt ROS / KOS.

Agents are contract-bound pipeline workers. They cannot persist results to a Case
without an explicit validation/persistence boundary outside this package.
"""

from agents.contract import (
    AgentArtifact,
    AgentContract,
    AgentProtocol,
    AgentRequest,
    AgentResourceLimits,
    ProvenanceRef,
)
from agents.registry import AgentRegistry

__all__ = [
    "AgentArtifact",
    "AgentContract",
    "AgentProtocol",
    "AgentRegistry",
    "AgentRequest",
    "AgentResourceLimits",
    "ProvenanceRef",
]
