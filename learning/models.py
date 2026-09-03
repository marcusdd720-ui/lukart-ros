"""Typed, immutable contracts for controlled learning candidates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class LearningSource(StrEnum):
    REASONING_KQM = "reasoning_kqm"
    EXTRACTION_KQM = "extraction_kqm"


class ChangeKind(StrEnum):
    CODE = "code"
    POLICY = "policy"
    PROMPT = "prompt"
    RETRIEVAL = "retrieval"
    ROUTING = "routing"
    RULE = "rule"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("metric name cannot be blank")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True, slots=True)
class MeasuredFailure:
    """Traceable observed failure derived from an evaluator, never raw model output."""

    failure_id: str
    source: LearningSource
    corpus_id: str
    corpus_version: str
    split: str
    evaluator_version: str
    source_sha: str
    case_id: str
    code: str
    expected: str
    actual: str
    result_digest: str
    report_digest: str

    def __post_init__(self) -> None:
        required = {
            "failure_id": self.failure_id,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "split": self.split,
            "evaluator_version": self.evaluator_version,
            "source_sha": self.source_sha,
            "case_id": self.case_id,
            "code": self.code,
            "expected": self.expected,
            "actual": self.actual,
            "result_digest": self.result_digest,
            "report_digest": self.report_digest,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} cannot be blank")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "actual": self.actual,
            "case_id": self.case_id,
            "code": self.code,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "evaluator_version": self.evaluator_version,
            "expected": self.expected,
            "failure_id": self.failure_id,
            "report_digest": self.report_digest,
            "result_digest": self.result_digest,
            "source": self.source.value,
            "source_sha": self.source_sha,
            "split": self.split,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class LearningCandidate:
    """A hypothesis for improvement, explicitly separated from trusted Product state."""

    candidate_id: str
    source_failure_digest: str
    target_component: str
    change_kind: ChangeKind
    problem_statement: str
    hypothesis: str
    success_criteria: tuple[str, ...]

    def __post_init__(self) -> None:
        required = {
            "candidate_id": self.candidate_id,
            "source_failure_digest": self.source_failure_digest,
            "target_component": self.target_component,
            "problem_statement": self.problem_statement,
            "hypothesis": self.hypothesis,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} cannot be blank")
        if not self.success_criteria or not all(item.strip() for item in self.success_criteria):
            raise ValueError("learning candidate requires explicit success criteria")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "change_kind": self.change_kind.value,
            "hypothesis": self.hypothesis,
            "problem_statement": self.problem_statement,
            "source_failure_digest": self.source_failure_digest,
            "success_criteria": list(self.success_criteria),
            "target_component": self.target_component,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
