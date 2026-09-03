"""Synthetic end-to-end gold harness for the controlled Product value loop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from agents.contract import AgentRequest
from agents.reference_fact import REFERENCE_FACT_AGENT_ID, ReferenceFactAgent
from agents.registry import AgentRegistry
from agents.runner import AgentRunner, AgentRunStatus
from knowledge.epistemic import KnowledgeStatus
from knowledge.provenance import EntityType, ExtractedFact
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact, ReasoningOutcome
from renderer import MarkdownReasoningRenderer
from validation.renderer_quality import RendererQualityReport, evaluate_reasoning_report


class EndToEndGoldSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    LOCKED_EVALUATION = "locked_evaluation"


_EXPECTED_SPLIT_SIZES = {
    EndToEndGoldSplit.DEVELOPMENT: 4,
    EndToEndGoldSplit.VALIDATION: 2,
    EndToEndGoldSplit.LOCKED_EVALUATION: 2,
}


class LockedEndToEndEvaluationError(RuntimeError):
    """Raised when locked E2E evaluation is requested without authorization."""


@dataclass(frozen=True, slots=True)
class EndToEndGoldCase:
    case_id: str
    split: EndToEndGoldSplit
    document_id: str
    document_text: str
    expected_entity_type: EntityType | None
    expected_value: str | None
    expected_outcome: ReasoningOutcome


@dataclass(frozen=True, slots=True)
class EndToEndGoldCorpus:
    corpus_id: str
    version: str
    status: str
    review_status: str
    cases: tuple[EndToEndGoldCase, ...]

    def cases_for_split(
        self,
        split: EndToEndGoldSplit,
        *,
        allow_locked: bool = False,
    ) -> tuple[EndToEndGoldCase, ...]:
        if split is EndToEndGoldSplit.LOCKED_EVALUATION and not allow_locked:
            raise LockedEndToEndEvaluationError(
                "locked E2E evaluation is disabled until explicit authorization"
            )
        return tuple(case for case in self.cases if case.split is split)


@dataclass(frozen=True, slots=True)
class EndToEndCaseResult:
    case_id: str
    agent_status: AgentRunStatus
    extraction_expectation_met: bool
    matched_fact_count: int
    reasoning_outcome: ReasoningOutcome
    expected_outcome: ReasoningOutcome
    renderer_quality: RendererQualityReport
    epistemic_fact_promotion_attempted: bool
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.agent_status is AgentRunStatus.PASS
            and self.extraction_expectation_met
            and self.reasoning_outcome is self.expected_outcome
            and self.renderer_quality.passed
            and not self.epistemic_fact_promotion_attempted
            and not self.errors
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "agent_status": self.agent_status.value,
            "case_id": self.case_id,
            "epistemic_fact_promotion_attempted": self.epistemic_fact_promotion_attempted,
            "errors": list(self.errors),
            "expected_outcome": self.expected_outcome.value,
            "extraction_expectation_met": self.extraction_expectation_met,
            "matched_fact_count": self.matched_fact_count,
            "reasoning_outcome": self.reasoning_outcome.value,
            "renderer_quality_digest": self.renderer_quality.digest(),
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class EndToEndSuiteMetrics:
    total_cases: int
    passed_cases: int
    agent_acceptance_rate: float
    extraction_expectation_accuracy: float
    reasoning_decision_accuracy: float
    renderer_quality_rate: float
    unsafe_fact_promotion_count: int


@dataclass(frozen=True, slots=True)
class EndToEndSuiteReport:
    corpus_id: str
    corpus_version: str
    split: EndToEndGoldSplit
    metrics: EndToEndSuiteMetrics
    case_results: tuple[EndToEndCaseResult, ...]
    locked_evaluation_executed: bool = False

    @property
    def passed(self) -> bool:
        return (
            self.metrics.total_cases > 0
            and self.metrics.passed_cases == self.metrics.total_cases
            and self.metrics.unsafe_fact_promotion_count == 0
            and not self.locked_evaluation_executed
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_results": [item.canonical_dict() for item in self.case_results],
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "locked_evaluation_executed": self.locked_evaluation_executed,
            "metrics": asdict(self.metrics),
            "split": self.split.value,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence")
    return value


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be null or non-empty text")
    return value.strip()


def load_e2e_gold_corpus(path: Path) -> EndToEndGoldCorpus:
    """Load the synthetic candidate corpus and preserve its review-pending state."""

    payload = _mapping(json.loads(path.read_text(encoding="utf-8")), "corpus")
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported E2E corpus schema")
    if payload.get("status") != "candidate_pending_independent_review":
        raise ValueError("E2E corpus must remain a review-pending candidate")
    if payload.get("review_status") != "not_reviewed":
        raise ValueError("E2E corpus cannot claim review without independent evidence")

    split_payload = _mapping(payload.get("splits"), "splits")
    split_by_case: dict[str, EndToEndGoldSplit] = {}
    for split, expected_size in _EXPECTED_SPLIT_SIZES.items():
        raw_ids = _sequence(split_payload.get(split.value), f"splits.{split.value}")
        ids = tuple(str(item) for item in raw_ids)
        if len(ids) != expected_size or len(set(ids)) != len(ids):
            raise ValueError(f"split {split.value!r} has invalid size or duplicate ids")
        for case_id in ids:
            if case_id in split_by_case:
                raise ValueError("E2E corpus splits must be disjoint")
            split_by_case[case_id] = split

    cases: list[EndToEndGoldCase] = []
    seen: set[str] = set()
    for raw_case_value in _sequence(payload.get("cases"), "cases"):
        raw_case = _mapping(raw_case_value, "case")
        case_id = str(raw_case.get("case_id", "")).strip()
        if not case_id.startswith("SYN-E2E-") or case_id in seen:
            raise ValueError(f"invalid or duplicate E2E case id: {case_id!r}")
        if case_id not in split_by_case:
            raise ValueError(f"E2E case is not assigned to a split: {case_id}")
        seen.add(case_id)

        expected_type_text = _optional_text(
            raw_case.get("expected_entity_type"),
            f"{case_id}.expected_entity_type",
        )
        expected_value = _optional_text(
            raw_case.get("expected_value"),
            f"{case_id}.expected_value",
        )
        if (expected_type_text is None) != (expected_value is None):
            raise ValueError("expected entity type and value must both be set or null")

        cases.append(
            EndToEndGoldCase(
                case_id=case_id,
                split=split_by_case[case_id],
                document_id=str(raw_case.get("document_id", "")).strip(),
                document_text=str(raw_case.get("document_text", "")),
                expected_entity_type=(
                    EntityType(expected_type_text) if expected_type_text is not None else None
                ),
                expected_value=expected_value,
                expected_outcome=ReasoningOutcome(str(raw_case.get("expected_outcome", ""))),
            )
        )

    if seen != set(split_by_case):
        raise ValueError("E2E corpus splits must partition the case set")
    if any(not case.document_id.startswith("SYN-DOC-") for case in cases):
        raise ValueError("E2E corpus may contain only synthetic document ids")

    return EndToEndGoldCorpus(
        corpus_id=str(payload.get("corpus_id", "")).strip(),
        version=str(payload.get("version", "")).strip(),
        status=str(payload["status"]),
        review_status=str(payload["review_status"]),
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )


def _runner() -> tuple[ReferenceFactAgent, AgentRunner]:
    agent = ReferenceFactAgent()
    registry = AgentRegistry()
    registry.register(agent)
    return agent, AgentRunner(registry)


def _facts_from_run_payload(payload: object) -> tuple[ExtractedFact, ...]:
    valid_payload = isinstance(payload, tuple) and all(
        isinstance(item, ExtractedFact) for item in payload
    )
    if not valid_payload:
        raise TypeError("ReferenceFactAgent returned an invalid fact payload")
    return cast(tuple[ExtractedFact, ...], payload)


def _matching_facts(
    case: EndToEndGoldCase,
    facts: tuple[ExtractedFact, ...],
) -> tuple[ExtractedFact, ...]:
    if case.expected_entity_type is None or case.expected_value is None:
        return ()
    return tuple(
        fact
        for fact in facts
        if fact.entity_type is case.expected_entity_type and fact.value == case.expected_value
    )


def _evidence_ref(fact: ExtractedFact) -> str:
    return (
        f"{fact.source_document_id}:{fact.source_document_sha256}:"
        f"{fact.char_start}-{fact.char_end}"
    )


def run_e2e_gold_case(case: EndToEndGoldCase) -> EndToEndCaseResult:
    """Execute Agent -> epistemic Reasoning -> final Renderer without EXTRACTED->FACT promotion."""

    agent, runner = _runner()
    request = AgentRequest(
        schema=agent.contract.input_schema,
        payload={
            "document_id": case.document_id,
            "document_type": "synthetic_gold",
            "text": case.document_text,
        },
        evidence_types=frozenset({"document_text"}),
    )
    run = runner.run(REFERENCE_FACT_AGENT_ID, agent.contract.version, request)
    if not run.accepted or run.artifact is None:
        fallback = ReasoningEngine(
            (
                ReasoningArtifact(
                    artifact_id="U-TARGET",
                    statement="Synthetic extraction target is unavailable.",
                    status=KnowledgeStatus.UNKNOWN,
                ),
                ReasoningArtifact(
                    artifact_id="C-TARGET",
                    statement="The synthetic extraction target is available.",
                    status=KnowledgeStatus.CONCLUSION,
                    support_ids=("U-TARGET",),
                ),
            )
        ).evaluate("C-TARGET")
        quality = evaluate_reasoning_report(MarkdownReasoningRenderer(), fallback)
        return EndToEndCaseResult(
            case_id=case.case_id,
            agent_status=run.status,
            extraction_expectation_met=False,
            matched_fact_count=0,
            reasoning_outcome=fallback.decision.outcome,
            expected_outcome=case.expected_outcome,
            renderer_quality=quality,
            epistemic_fact_promotion_attempted=False,
            errors=run.errors,
        )

    facts = _facts_from_run_payload(run.artifact.payload)
    matches = _matching_facts(case, facts)
    expects_target = case.expected_entity_type is not None
    extraction_expectation_met = bool(matches) if expects_target else not facts

    if matches:
        support = ReasoningArtifact(
            artifact_id="CL-TARGET",
            statement="The expected synthetic token was extracted from source text.",
            status=KnowledgeStatus.CLAIM,
            evidence_refs=tuple(_evidence_ref(fact) for fact in matches),
            rationale="EXTRACTED output is represented as a claim, not promoted to FACT.",
        )
    else:
        support = ReasoningArtifact(
            artifact_id="U-TARGET",
            statement="The expected synthetic extraction target is unavailable.",
            status=KnowledgeStatus.UNKNOWN,
            rationale="No matching extracted token is available for the target.",
        )

    conclusion = ReasoningArtifact(
        artifact_id="C-TARGET",
        statement="The expected synthetic extraction token is available.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(support.artifact_id,),
    )
    reasoning = ReasoningEngine((support, conclusion)).evaluate(conclusion.artifact_id)
    quality = evaluate_reasoning_report(MarkdownReasoningRenderer(), reasoning)
    errors: list[str] = []
    if not extraction_expectation_met:
        errors.append("EXTRACTION_EXPECTATION_MISMATCH")
    if reasoning.decision.outcome is not case.expected_outcome:
        errors.append("REASONING_OUTCOME_MISMATCH")
    if not quality.passed:
        errors.append("RENDERER_QUALITY_FAILED")

    return EndToEndCaseResult(
        case_id=case.case_id,
        agent_status=run.status,
        extraction_expectation_met=extraction_expectation_met,
        matched_fact_count=len(matches),
        reasoning_outcome=reasoning.decision.outcome,
        expected_outcome=case.expected_outcome,
        renderer_quality=quality,
        epistemic_fact_promotion_attempted=False,
        errors=tuple(errors),
    )


def evaluate_e2e_split(
    corpus: EndToEndGoldCorpus,
    split: EndToEndGoldSplit,
) -> EndToEndSuiteReport:
    """Evaluate development/validation only; locked execution stays sealed."""

    cases = corpus.cases_for_split(split)
    results = tuple(run_e2e_gold_case(case) for case in cases)
    total = len(results)
    if total == 0:
        raise ValueError("E2E split cannot be empty")

    metrics = EndToEndSuiteMetrics(
        total_cases=total,
        passed_cases=sum(item.passed for item in results),
        agent_acceptance_rate=sum(
            item.agent_status is AgentRunStatus.PASS for item in results
        )
        / total,
        extraction_expectation_accuracy=sum(
            item.extraction_expectation_met for item in results
        )
        / total,
        reasoning_decision_accuracy=sum(
            item.reasoning_outcome is item.expected_outcome for item in results
        )
        / total,
        renderer_quality_rate=sum(item.renderer_quality.passed for item in results) / total,
        unsafe_fact_promotion_count=sum(
            item.epistemic_fact_promotion_attempted for item in results
        ),
    )
    return EndToEndSuiteReport(
        corpus_id=corpus.corpus_id,
        corpus_version=corpus.version,
        split=split,
        metrics=metrics,
        case_results=results,
        locked_evaluation_executed=False,
    )
