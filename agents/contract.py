"""Typed execution contract for controlled pipeline agents."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from core.models.ids import AgentId
from knowledge.provenance import EpistemicStatus

_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True, slots=True)
class AgentResourceLimits:
    """Hard resource budget declared by an Agent Step Contract."""

    max_runtime_seconds: float
    max_model_calls: int = 0
    max_cost_units: float = 0.0

    def __post_init__(self) -> None:
        if self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be > 0")
        if self.max_model_calls < 0:
            raise ValueError("max_model_calls must be >= 0")
        if self.max_cost_units < 0:
            raise ValueError("max_cost_units must be >= 0")


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    """Minimal reproducible source pointer emitted by an agent."""

    source_document_id: str
    source_document_sha256: str
    page: int
    char_start: int
    char_end: int

    def __post_init__(self) -> None:
        if not self.source_document_id.strip():
            raise ValueError("source_document_id is required")
        if len(self.source_document_sha256) != 64:
            raise ValueError("source_document_sha256 must be a SHA-256 hex digest")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("invalid provenance character span")


@dataclass(frozen=True, slots=True)
class AgentContract:
    """Formal, immutable contract that defines one executable agent version."""

    agent_id: AgentId
    name: str
    version: str
    input_schema: str
    output_schema: str
    required_evidence_types: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    allowed_epistemic_statuses: tuple[EpistemicStatus, ...]
    validation_gates: tuple[str, ...]
    resource_limits: AgentResourceLimits
    provenance_required: bool = True
    deterministic: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("agent name is required")
        if not _SEMVER_RE.fullmatch(self.version):
            raise ValueError("agent version must use MAJOR.MINOR.PATCH semver")
        if not self.input_schema.strip() or not self.output_schema.strip():
            raise ValueError("input_schema and output_schema are required")
        overlap = set(self.allowed_operations).intersection(self.forbidden_operations)
        if overlap:
            raise ValueError(f"operations cannot be both allowed and forbidden: {sorted(overlap)}")
        if not self.validation_gates:
            raise ValueError("at least one validation gate is required")
        if not self.allowed_epistemic_statuses:
            raise ValueError("at least one epistemic status must be allowed")


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """Validated input envelope presented to an agent runner."""

    schema: str
    payload: Mapping[str, object]
    evidence_types: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class AgentArtifact:
    """Immutable output envelope. Persistence into Case is intentionally external."""

    agent_id: AgentId
    agent_version: str
    artifact_type: str
    payload: object
    provenance: tuple[ProvenanceRef, ...] = ()
    epistemic_statuses: tuple[EpistemicStatus, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


class AgentProtocol(Protocol):
    """Minimum interface required by the controlled Agent Runner."""

    @property
    def contract(self) -> AgentContract: ...

    def execute(self, request: AgentRequest) -> AgentArtifact: ...
