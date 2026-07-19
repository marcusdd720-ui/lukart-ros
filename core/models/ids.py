"""
KOS - Shared Identifier Types

This module defines strongly typed identifiers used across the
Knowledge Operating System.

Using dedicated ID types prevents accidental mixing of unrelated UUIDs
(e.g. WorkflowId vs DocumentId) while remaining runtime-compatible with UUID.
"""

from __future__ import annotations

from typing import NewType
from uuid import UUID, uuid4


# ============================================================================
# Generic Entity ID
# ============================================================================

EntityId = NewType("EntityId", UUID)


# ============================================================================
# Domain IDs
# ============================================================================

DocumentId = NewType("DocumentId", UUID)

ArtifactId = NewType("ArtifactId", UUID)

WorkflowId = NewType("WorkflowId", UUID)

TaskId = NewType("TaskId", UUID)

DecisionId = NewType("DecisionId", UUID)

EvidenceId = NewType("EvidenceId", UUID)

EventId = NewType("EventId", UUID)

NodeId = NewType("NodeId", UUID)

EdgeId = NewType("EdgeId", UUID)

PluginId = NewType("PluginId", UUID)

AgentId = NewType("AgentId", UUID)

ReportId = NewType("ReportId", UUID)

CaseId = NewType("CaseId", UUID)


# ============================================================================
# Factory
# ============================================================================


def new_entity_id() -> EntityId:
    """Create a new generic entity identifier."""
    return EntityId(uuid4())


def new_document_id() -> DocumentId:
    """Create a new document identifier."""
    return DocumentId(uuid4())


def new_artifact_id() -> ArtifactId:
    """Create a new artifact identifier."""
    return ArtifactId(uuid4())


def new_workflow_id() -> WorkflowId:
    """Create a new workflow identifier."""
    return WorkflowId(uuid4())


def new_task_id() -> TaskId:
    """Create a new task identifier."""
    return TaskId(uuid4())


def new_decision_id() -> DecisionId:
    """Create a new decision identifier."""
    return DecisionId(uuid4())


def new_evidence_id() -> EvidenceId:
    """Create a new evidence identifier."""
    return EvidenceId(uuid4())


def new_event_id() -> EventId:
    """Create a new event identifier."""
    return EventId(uuid4())


def new_node_id() -> NodeId:
    """Create a new graph node identifier."""
    return NodeId(uuid4())


def new_edge_id() -> EdgeId:
    """Create a new graph edge identifier."""
    return EdgeId(uuid4())


def new_plugin_id() -> PluginId:
    """Create a new plugin identifier."""
    return PluginId(uuid4())


def new_agent_id() -> AgentId:
    """Create a new AI agent identifier."""
    return AgentId(uuid4())


def new_report_id() -> ReportId:
    """Create a new report identifier."""
    return ReportId(uuid4())


def new_case_id() -> CaseId:
    """Create a new legal case identifier."""
    return CaseId(uuid4())