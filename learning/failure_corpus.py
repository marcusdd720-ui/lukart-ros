"""Failure-corpus construction from measured evaluator output only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from learning.models import LearningSource, MeasuredFailure
from validation.reasoning_gold import ReasoningGoldSplit
from validation.reasoning_kqm import ReasoningKQMReport


class LockedLearningSourceError(RuntimeError):
    """Raised when locked evaluation output is proposed as learning input."""


@dataclass(frozen=True, slots=True)
class FailureCorpus:
    corpus_id: str
    version: str
    source_report_digest: str
    failures: tuple[MeasuredFailure, ...]

    def __post_init__(self) -> None:
        if not self.corpus_id.strip() or not self.version.strip():
            raise ValueError("failure corpus id/version cannot be blank")
        if not self.source_report_digest.strip():
            raise ValueError("failure corpus requires source report digest")
        ids = [failure.failure_id for failure in self.failures]
        if len(ids) != len(set(ids)):
            raise ValueError("failure corpus contains duplicate failure ids")


def reasoning_report_digest(report: ReasoningKQMReport) -> str:
    payload = {
        "corpus_id": report.corpus_id,
        "corpus_version": report.corpus_version,
        "engine_version": report.engine_version,
        "evaluator_version": report.evaluator_version,
        "failures": [
            {
                "actual": failure.actual,
                "case_id": failure.case_id,
                "code": failure.code,
                "expected": failure.expected,
            }
            for failure in report.failures
        ],
        "locked_evaluation_executed": report.locked_evaluation_executed,
        "metrics": {
            "abstention_recall": report.metrics.abstention_recall,
            "correct_decisions": report.metrics.correct_decisions,
            "decision_accuracy": report.metrics.decision_accuracy,
            "expected_abstain": report.metrics.expected_abstain,
            "expected_conclude": report.metrics.expected_conclude,
            "false_conclude": report.metrics.false_conclude,
            "open_question_coverage": report.metrics.open_question_coverage,
            "total_cases": report.metrics.total_cases,
            "true_conclude": report.metrics.true_conclude,
            "unsafe_conclusion_rate": report.metrics.unsafe_conclusion_rate,
            "valid_conclusion_recall": report.metrics.valid_conclusion_recall,
        },
        "result_digests": [list(item) for item in report.result_digests],
        "split": report.split.value,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def failure_corpus_from_reasoning(
    report: ReasoningKQMReport,
    *,
    source_sha: str,
    failure_corpus_version: str = "1.0.0",
) -> FailureCorpus:
    """Convert measured reasoning failures into learning-safe, traceable observations."""

    if not source_sha.strip():
        raise ValueError("source SHA is required")
    if report.locked_evaluation_executed or report.split is ReasoningGoldSplit.LOCKED_EVALUATION:
        raise LockedLearningSourceError("locked evaluation must never become tuning input")

    digest_by_case = dict(report.result_digests)
    report_digest = reasoning_report_digest(report)
    failures: list[MeasuredFailure] = []
    for index, failure in enumerate(report.failures, start=1):
        result_digest = digest_by_case.get(failure.case_id)
        if not result_digest:
            raise ValueError(
                f"measured failure lacks result digest for case: {failure.case_id}"
            )
        failures.append(
            MeasuredFailure(
                failure_id=f"MF-{report.corpus_id}-{failure.case_id}-{index:03d}",
                source=LearningSource.REASONING_KQM,
                corpus_id=report.corpus_id,
                corpus_version=report.corpus_version,
                split=report.split.value,
                evaluator_version=report.evaluator_version,
                source_sha=source_sha,
                case_id=failure.case_id,
                code=failure.code,
                expected=failure.expected,
                actual=failure.actual,
                result_digest=result_digest,
                report_digest=report_digest,
            )
        )

    return FailureCorpus(
        corpus_id=f"failure-{report.corpus_id}-{report.split.value}",
        version=failure_corpus_version,
        source_report_digest=report_digest,
        failures=tuple(failures),
    )
