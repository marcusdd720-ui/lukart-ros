"""Typed, immutable contracts for controlled learning candidates."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _required_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be blank")
    return normalized


def _require_sha256(name: str, value: str) -> str:
    normalized = _required_text(name, value).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a 64-character SHA-256 digest")
    return normalized


def _require_git_sha(value: str) -> str:
    normalized = _required_text("source_sha", value).lower()
    if not _GIT_SHA_RE.fullmatch(normalized):
        raise ValueError("source_sha must be a 40-64 character hexadecimal commit SHA")
    return normalized


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
        object.__setattr__(self, "name", _required_text("metric name", self.name))
        if not math.isfinite(self.value):
            raise ValueError("metric value must be finite")


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
        for field_name in (
            "failure_id",
            "corpus_id",
            "corpus_version",
            "split",
            "evaluator_version",
            "case_id",
            "code",
            "expected",
            "actual",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(field_name, str(getattr(self, field_name))),
            )
        object.__setattr__(self, "source_sha", _require_git_sha(self.source_sha))
        object.__setattr__(
            self,
            "result_digest",
            _require_sha256("result_digest", self.result_digest),
        )
        object.__setattr__(
            self,
            "report_digest",
            _require_sha256("report_digest", self.report_digest),
        )

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
        for field_name in (
            "candidate_id",
            "target_component",
            "problem_statement",
            "hypothesis",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(field_name, str(getattr(self, field_name))),
            )
        object.__setattr__(
            self,
            "source_failure_digest",
            _require_sha256("source_failure_digest", self.source_failure_digest),
        )
        criteria = tuple(item.strip() for item in self.success_criteria)
        if not criteria or not all(criteria):
            raise ValueError("learning candidate requires explicit success criteria")
        if len(criteria) != len(set(criteria)):
            raise ValueError("learning candidate success criteria must be unique")
        object.__setattr__(self, "success_criteria", criteria)

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
