"""Typed reasoning artifacts and deterministic result contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum

from knowledge.epistemic import KnowledgeStatus


class ReasoningOutcome(StrEnum):
    CONCLUDE = "CONCLUDE"
    ABSTAIN = "ABSTAIN"


def _normalized_refs(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain blank values")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ReasoningArtifact:
    """One explicit epistemic statement with provenance and support links."""

    artifact_id: str
    statement: str
    status: KnowledgeStatus
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    support_ids: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""

    def __post_init__(self) -> None:
        artifact_id = self.artifact_id.strip()
        statement = self.statement.strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")
        if not statement:
            raise ValueError("statement is required")

        evidence_refs = _normalized_refs(self.evidence_refs, field_name="evidence_refs")
        support_ids = _normalized_refs(self.support_ids, field_name="support_ids")
        if artifact_id in support_ids:
            raise ValueError("artifact cannot support itself")

        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "support_ids", support_ids)
        object.__setattr__(self, "rationale", self.rationale.strip())

    def canonical_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "statement": self.statement,
            "status": self.status.value,
            "evidence_refs": list(sorted(self.evidence_refs)),
            "support_ids": list(sorted(self.support_ids)),
            "rationale": self.rationale,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    """An unresolved information need that must remain visible."""

    question_id: str
    question: str
    reason: str
    related_artifact_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        question_id = self.question_id.strip()
        question = self.question.strip()
        reason = self.reason.strip()
        if not question_id or not question or not reason:
            raise ValueError("open question id, question and reason are required")
        related = _normalized_refs(
            self.related_artifact_ids,
            field_name="related_artifact_ids",
        )
        object.__setattr__(self, "question_id", question_id)
        object.__setattr__(self, "question", question)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "related_artifact_ids", related)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "reason": self.reason,
            "related_artifact_ids": list(sorted(self.related_artifact_ids)),
        }


@dataclass(frozen=True, slots=True)
class ReasoningDecision:
    outcome: ReasoningOutcome
    reason: str
    artifact_id: str | None = None
    open_question_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValueError("reason is required")
        if self.outcome is ReasoningOutcome.CONCLUDE and not self.artifact_id:
            raise ValueError("CONCLUDE requires artifact_id")
        if self.outcome is ReasoningOutcome.ABSTAIN and self.artifact_id is not None:
            raise ValueError("ABSTAIN cannot identify a concluded artifact")
        question_ids = _normalized_refs(
            self.open_question_ids,
            field_name="open_question_ids",
        )
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "open_question_ids", question_ids)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "artifact_id": self.artifact_id,
            "open_question_ids": list(sorted(self.open_question_ids)),
        }


@dataclass(frozen=True, slots=True)
class ReasoningRunResult:
    """Renderer-ready, deterministic reasoning result."""

    artifacts: tuple[ReasoningArtifact, ...]
    open_questions: tuple[OpenQuestion, ...]
    decision: ReasoningDecision
    schema: str = "lukart.reasoning-result.v1"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "artifacts": [
                artifact.canonical_dict()
                for artifact in sorted(self.artifacts, key=lambda item: item.artifact_id)
            ],
            "open_questions": [
                question.canonical_dict()
                for question in sorted(self.open_questions, key=lambda item: item.question_id)
            ],
            "decision": self.decision.canonical_dict(),
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
