"""Contracts and loader for the synthetic reasoning gold corpus."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from knowledge.epistemic import KnowledgeStatus
from reasoning.models import ReasoningArtifact, ReasoningOutcome


class ReasoningGoldSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    LOCKED_EVALUATION = "locked_evaluation"


EXPECTED_SPLIT_SIZES = {
    ReasoningGoldSplit.DEVELOPMENT: 4,
    ReasoningGoldSplit.VALIDATION: 2,
    ReasoningGoldSplit.LOCKED_EVALUATION: 2,
}


class LockedReasoningEvaluationError(RuntimeError):
    """Raised when locked reasoning evaluation is requested without authorization."""


@dataclass(frozen=True, slots=True)
class ReasoningGoldCase:
    case_id: str
    split: ReasoningGoldSplit
    conclusion_id: str
    artifacts: tuple[ReasoningArtifact, ...]
    expected_outcome: ReasoningOutcome
    expected_min_open_questions: int


@dataclass(frozen=True, slots=True)
class ReasoningGoldCorpus:
    corpus_id: str
    version: str
    status: str
    review_status: str
    cases: tuple[ReasoningGoldCase, ...]

    def cases_for_split(
        self,
        split: ReasoningGoldSplit,
        *,
        allow_locked: bool = False,
    ) -> tuple[ReasoningGoldCase, ...]:
        if split is ReasoningGoldSplit.LOCKED_EVALUATION and not allow_locked:
            raise LockedReasoningEvaluationError(
                "locked reasoning evaluation is disabled until review/freeze authorization"
            )
        return tuple(case for case in self.cases if case.split is split)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence")
    return value


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    return tuple(str(item) for item in _sequence(value, field_name))


def _parse_artifact(raw: Mapping[str, object]) -> ReasoningArtifact:
    return ReasoningArtifact(
        artifact_id=str(raw.get("artifact_id", "")),
        statement=str(raw.get("statement", "")),
        status=KnowledgeStatus(str(raw.get("status", ""))),
        evidence_refs=_string_tuple(raw.get("evidence_refs", []), "evidence_refs"),
        support_ids=_string_tuple(raw.get("support_ids", []), "support_ids"),
        rationale=str(raw.get("rationale", "")),
    )


def load_reasoning_gold_corpus(path: Path) -> ReasoningGoldCorpus:
    """Load and fail-closed validate the candidate reasoning benchmark."""

    payload = _mapping(json.loads(path.read_text(encoding="utf-8")), "corpus")
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported reasoning corpus schema")
    if payload.get("status") != "candidate_pending_independent_review":
        raise ValueError("reasoning corpus must remain a review-pending candidate")
    if payload.get("review_status") != "not_reviewed":
        raise ValueError("reasoning corpus cannot claim review without independent evidence")

    corpus_id = str(payload.get("corpus_id", "")).strip()
    version = str(payload.get("version", "")).strip()
    if not corpus_id.startswith("reasoning-gold-") or not version:
        raise ValueError("reasoning corpus id/version is invalid")

    split_payload = _mapping(payload.get("splits"), "splits")
    split_by_case: dict[str, ReasoningGoldSplit] = {}
    for split, expected_size in EXPECTED_SPLIT_SIZES.items():
        ids = _string_tuple(split_payload.get(split.value), f"splits.{split.value}")
        if len(ids) != expected_size or len(set(ids)) != len(ids):
            raise ValueError(f"split {split.value!r} has invalid size or duplicate ids")
        for case_id in ids:
            if case_id in split_by_case:
                raise ValueError("reasoning corpus splits must be disjoint")
            split_by_case[case_id] = split

    cases: list[ReasoningGoldCase] = []
    seen_case_ids: set[str] = set()
    for raw_case_value in _sequence(payload.get("cases"), "cases"):
        raw_case = _mapping(raw_case_value, "case")
        case_id = str(raw_case.get("case_id", "")).strip()
        if not case_id.startswith("SYN-R-"):
            raise ValueError(f"non-synthetic reasoning case id: {case_id!r}")
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate reasoning case id: {case_id}")
        if case_id not in split_by_case:
            raise ValueError(f"reasoning case is not assigned to a split: {case_id}")
        seen_case_ids.add(case_id)

        raw_artifacts = _sequence(raw_case.get("artifacts"), f"{case_id}.artifacts")
        artifacts = tuple(
            _parse_artifact(_mapping(raw_artifact, f"{case_id}.artifact"))
            for raw_artifact in raw_artifacts
        )
        if not artifacts:
            raise ValueError(f"reasoning case has no artifacts: {case_id}")

        raw_min_questions = raw_case.get("expected_min_open_questions", 0)
        if not isinstance(raw_min_questions, int) or isinstance(raw_min_questions, bool):
            raise ValueError("expected_min_open_questions must be an integer")
        if raw_min_questions < 0:
            raise ValueError("expected_min_open_questions cannot be negative")

        cases.append(
            ReasoningGoldCase(
                case_id=case_id,
                split=split_by_case[case_id],
                conclusion_id=str(raw_case.get("conclusion_id", "")).strip(),
                artifacts=artifacts,
                expected_outcome=ReasoningOutcome(str(raw_case.get("expected_outcome", ""))),
                expected_min_open_questions=raw_min_questions,
            )
        )

    if seen_case_ids != set(split_by_case):
        raise ValueError("reasoning corpus splits must partition the case set")

    return ReasoningGoldCorpus(
        corpus_id=corpus_id,
        version=version,
        status=str(payload["status"]),
        review_status=str(payload["review_status"]),
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )
