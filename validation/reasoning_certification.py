"""Fail-closed Step 6 reasoning certification with pre-registered locked-use policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningOutcome
from reasoning.validation import validate_reasoning_graph
from validation.reasoning_gold import (
    ReasoningGoldCase,
    ReasoningGoldCorpus,
    ReasoningGoldSplit,
    load_reasoning_gold_corpus,
)
from validation.reasoning_kqm import ReasoningKQMReport, evaluate_reasoning_split


class ReasoningCertificationError(RuntimeError):
    """Raised when Step 6 cannot proceed truthfully."""


@dataclass(frozen=True, slots=True)
class CertificationThresholds:
    decision_accuracy_min: float
    valid_conclusion_recall_min: float
    abstention_recall_min: float
    unsafe_conclusion_rate_max: float
    open_question_coverage_min: float
    contradiction_case_pass_rate_min: float


@dataclass(frozen=True, slots=True)
class ReasoningCertificationPolicy:
    schema_version: str
    policy_id: str
    corpus_id: str
    corpus_sha256: str
    engine_version: str
    evaluator_version: str
    locked_use: str
    locked_evaluation_authorized: bool
    authorized_by: str
    authorization_date: str
    authorization_reason: str
    contradiction_case_ids: tuple[str, ...]
    thresholds: CertificationThresholds
    interpretation_boundary: str


@dataclass(frozen=True, slots=True)
class ContradictionMeasurement:
    case_id: str
    expected_outcome: str
    actual_outcome: str
    contradiction_detected: bool
    passed: bool


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReasoningCertificationError(f"{field_name} must be an object")
    return value


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReasoningCertificationError(f"{key} must be non-empty text")
    return value.strip()


def _require_float(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ReasoningCertificationError(f"{key} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ReasoningCertificationError(f"{key} must be between 0 and 1")
    return result


def load_certification_policy(path: Path) -> ReasoningCertificationPolicy:
    try:
        payload_value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReasoningCertificationError(f"invalid certification policy: {path}") from exc
    payload = _mapping(payload_value, "policy")

    if payload.get("schema_version") != "1.0":
        raise ReasoningCertificationError("unsupported certification policy schema")
    if payload.get("locked_evaluation_authorized") is not True:
        raise ReasoningCertificationError("locked evaluation is not explicitly authorized")
    if payload.get("locked_use") != "certification_only":
        raise ReasoningCertificationError("locked evaluation must be certification-only")

    raw_ids = payload.get("contradiction_case_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ReasoningCertificationError("contradiction_case_ids are required")
    contradiction_case_ids = tuple(str(item).strip() for item in raw_ids)
    if any(not item for item in contradiction_case_ids):
        raise ReasoningCertificationError("contradiction_case_ids cannot contain blanks")
    if len(set(contradiction_case_ids)) != len(contradiction_case_ids):
        raise ReasoningCertificationError("contradiction_case_ids cannot contain duplicates")

    thresholds_payload = _mapping(payload.get("thresholds"), "thresholds")
    thresholds = CertificationThresholds(
        decision_accuracy_min=_require_float(
            thresholds_payload, "decision_accuracy_min"
        ),
        valid_conclusion_recall_min=_require_float(
            thresholds_payload, "valid_conclusion_recall_min"
        ),
        abstention_recall_min=_require_float(
            thresholds_payload, "abstention_recall_min"
        ),
        unsafe_conclusion_rate_max=_require_float(
            thresholds_payload, "unsafe_conclusion_rate_max"
        ),
        open_question_coverage_min=_require_float(
            thresholds_payload, "open_question_coverage_min"
        ),
        contradiction_case_pass_rate_min=_require_float(
            thresholds_payload, "contradiction_case_pass_rate_min"
        ),
    )

    return ReasoningCertificationPolicy(
        schema_version="1.0",
        policy_id=_require_text(payload, "policy_id"),
        corpus_id=_require_text(payload, "corpus_id"),
        corpus_sha256=_require_text(payload, "corpus_sha256"),
        engine_version=_require_text(payload, "engine_version"),
        evaluator_version=_require_text(payload, "evaluator_version"),
        locked_use="certification_only",
        locked_evaluation_authorized=True,
        authorized_by=_require_text(payload, "authorized_by"),
        authorization_date=_require_text(payload, "authorization_date"),
        authorization_reason=_require_text(payload, "authorization_reason"),
        contradiction_case_ids=contradiction_case_ids,
        thresholds=thresholds,
        interpretation_boundary=_require_text(payload, "interpretation_boundary"),
    )


def validate_frozen_reasoning_corpus(
    *,
    corpus_path: Path,
    review_path: Path,
    freeze_path: Path,
    policy: ReasoningCertificationPolicy,
) -> None:
    corpus_sha256 = sha256_file(corpus_path)
    if corpus_sha256 != policy.corpus_sha256:
        raise ReasoningCertificationError("policy is not bound to current reasoning corpus")

    try:
        review_value = json.loads(review_path.read_text(encoding="utf-8"))
        freeze_value = json.loads(freeze_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReasoningCertificationError("review/freeze artifact is invalid") from exc
    review = _mapping(review_value, "review")
    freeze = _mapping(freeze_value, "freeze")

    if review.get("corpus_id") != policy.corpus_id:
        raise ReasoningCertificationError("review corpus id does not match policy")
    if review.get("corpus_sha256") != corpus_sha256:
        raise ReasoningCertificationError("review hash does not match reasoning corpus")
    if review.get("reviewer_kind") != "human":
        raise ReasoningCertificationError("reasoning review must be human")
    if review.get("reviewer_independent") is not True:
        raise ReasoningCertificationError("reasoning review must be independent")
    if review.get("decision") != "APPROVED" or review.get("freeze_approved") is not True:
        raise ReasoningCertificationError("reasoning corpus is not approved for freeze")

    canonical_review = json.dumps(review, sort_keys=True, separators=(",", ":")).encode()
    expected_review_digest = hashlib.sha256(canonical_review).hexdigest()
    expected_freeze = {
        "schema_version": "1.0",
        "corpus_id": policy.corpus_id,
        "corpus_sha256": corpus_sha256,
        "status": "FROZEN",
        "reviewer_id": review.get("reviewer_id"),
        "review_digest": expected_review_digest,
    }
    for key, expected in expected_freeze.items():
        if freeze.get(key) != expected:
            raise ReasoningCertificationError(
                f"freeze manifest field {key} does not match reviewed corpus"
            )


def _case_by_id(corpus: ReasoningGoldCorpus, case_id: str) -> ReasoningGoldCase:
    for case in corpus.cases:
        if case.case_id == case_id:
            return case
    raise ReasoningCertificationError(f"certification case not found: {case_id}")


def measure_contradiction_handling(
    corpus: ReasoningGoldCorpus,
    policy: ReasoningCertificationPolicy,
) -> tuple[ContradictionMeasurement, ...]:
    measurements: list[ContradictionMeasurement] = []
    for case_id in policy.contradiction_case_ids:
        case = _case_by_id(corpus, case_id)
        if case.split is ReasoningGoldSplit.LOCKED_EVALUATION:
            raise ReasoningCertificationError(
                "contradiction measurement must not consume locked cases"
            )
        validation = validate_reasoning_graph(case.artifacts)
        contradiction_detected = any(issue.code == "R003" for issue in validation.issues)
        actual = ReasoningEngine(case.artifacts).evaluate(case.conclusion_id).decision.outcome
        passed = (
            contradiction_detected
            and case.expected_outcome is ReasoningOutcome.ABSTAIN
            and actual is ReasoningOutcome.ABSTAIN
        )
        measurements.append(
            ContradictionMeasurement(
                case_id=case_id,
                expected_outcome=case.expected_outcome.value,
                actual_outcome=actual.value,
                contradiction_detected=contradiction_detected,
                passed=passed,
            )
        )
    return tuple(measurements)


def certification_readiness(
    *,
    corpus_path: Path,
    review_path: Path,
    freeze_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    policy = load_certification_policy(policy_path)
    validate_frozen_reasoning_corpus(
        corpus_path=corpus_path,
        review_path=review_path,
        freeze_path=freeze_path,
        policy=policy,
    )
    corpus = load_reasoning_gold_corpus(corpus_path)
    if corpus.corpus_id != policy.corpus_id:
        raise ReasoningCertificationError("loaded corpus id does not match policy")

    contradiction = measure_contradiction_handling(corpus, policy)
    contradiction_pass_rate = sum(item.passed for item in contradiction) / len(contradiction)
    ready = contradiction_pass_rate >= policy.thresholds.contradiction_case_pass_rate_min
    return {
        "ready": ready,
        "locked_evaluation_executed": False,
        "corpus_sha256": sha256_file(corpus_path),
        "policy_sha256": sha256_file(policy_path),
        "freeze_sha256": sha256_file(freeze_path),
        "contradiction_pass_rate": contradiction_pass_rate,
        "contradiction_measurements": [asdict(item) for item in contradiction],
    }


def _metric_checks(
    report: ReasoningKQMReport,
    thresholds: CertificationThresholds,
) -> dict[str, bool]:
    metrics = report.metrics
    return {
        "decision_accuracy": metrics.decision_accuracy >= thresholds.decision_accuracy_min,
        "valid_conclusion_recall": (
            metrics.valid_conclusion_recall >= thresholds.valid_conclusion_recall_min
        ),
        "abstention_recall": metrics.abstention_recall >= thresholds.abstention_recall_min,
        "unsafe_conclusion_rate": (
            metrics.unsafe_conclusion_rate <= thresholds.unsafe_conclusion_rate_max
        ),
        "open_question_coverage": (
            metrics.open_question_coverage >= thresholds.open_question_coverage_min
        ),
        "evaluation_failures_zero": not report.failures,
    }


def _report_metrics(report: ReasoningKQMReport) -> dict[str, object]:
    return {
        "total_cases": report.metrics.total_cases,
        "correct_decisions": report.metrics.correct_decisions,
        "decision_accuracy": report.metrics.decision_accuracy,
        "valid_conclusion_recall": report.metrics.valid_conclusion_recall,
        "abstention_recall": report.metrics.abstention_recall,
        "unsafe_conclusion_rate": report.metrics.unsafe_conclusion_rate,
        "open_question_coverage": report.metrics.open_question_coverage,
        "failure_count": len(report.failures),
        "failures": [asdict(item) for item in report.failures],
        "result_digests": [list(item) for item in report.result_digests],
    }


def run_locked_certification(
    *,
    corpus_path: Path,
    review_path: Path,
    freeze_path: Path,
    policy_path: Path,
    validated_sha: str,
) -> dict[str, object]:
    if len(validated_sha) != 40 or any(ch not in "0123456789abcdef" for ch in validated_sha):
        raise ReasoningCertificationError("validated_sha must be a full lowercase Git SHA")

    readiness = certification_readiness(
        corpus_path=corpus_path,
        review_path=review_path,
        freeze_path=freeze_path,
        policy_path=policy_path,
    )
    if readiness["ready"] is not True:
        raise ReasoningCertificationError("pre-locked certification readiness failed")

    policy = load_certification_policy(policy_path)
    corpus = load_reasoning_gold_corpus(corpus_path)

    development = evaluate_reasoning_split(
        corpus,
        ReasoningGoldSplit.DEVELOPMENT,
        engine_version=policy.engine_version,
        evaluator_version=policy.evaluator_version,
    )
    validation = evaluate_reasoning_split(
        corpus,
        ReasoningGoldSplit.VALIDATION,
        engine_version=policy.engine_version,
        evaluator_version=policy.evaluator_version,
    )
    locked = evaluate_reasoning_split(
        corpus,
        ReasoningGoldSplit.LOCKED_EVALUATION,
        engine_version=policy.engine_version,
        evaluator_version=policy.evaluator_version,
        allow_locked=True,
    )

    split_checks = {
        "development": _metric_checks(development, policy.thresholds),
        "validation": _metric_checks(validation, policy.thresholds),
        "locked_evaluation": _metric_checks(locked, policy.thresholds),
    }
    all_split_checks_pass = all(
        all(checks.values()) for checks in split_checks.values()
    )
    raw_contradiction_pass_rate = readiness.get("contradiction_pass_rate")
    if not isinstance(raw_contradiction_pass_rate, (int, float)) or isinstance(
        raw_contradiction_pass_rate, bool
    ):
        raise ReasoningCertificationError("contradiction pass rate is invalid")
    contradiction_pass_rate = float(raw_contradiction_pass_rate)
    contradiction_pass = (
        contradiction_pass_rate >= policy.thresholds.contradiction_case_pass_rate_min
    )
    passed = all_split_checks_pass and contradiction_pass

    check_status = "PASS" if passed else "FAIL"
    checks = [
        {"name": "frozen_reasoning_corpus_bound", "status": "PASS"},
        {
            "name": "reasoning_metrics_recorded",
            "status": check_status if all_split_checks_pass else "FAIL",
        },
        {
            "name": "abstention_measured",
            "status": (
                "PASS"
                if all(
                    checks["abstention_recall"]
                    for checks in split_checks.values()
                )
                else "FAIL"
            ),
        },
        {
            "name": "contradiction_handling_measured",
            "status": "PASS" if contradiction_pass else "FAIL",
        },
        {
            "name": "certification_decision_recorded",
            "status": check_status,
        },
    ]

    return {
        "schema_version": "1.0",
        "step": 6,
        "status": "PASS" if passed else "FAIL",
        "validated_sha": validated_sha,
        "gate_kind": "certification",
        "evidence_kind": "reasoning_certification",
        "locked_evaluation_used_for_tuning": False,
        "private_data_committed": False,
        "locked_evaluation_executed": True,
        "policy_id": policy.policy_id,
        "policy_sha256": sha256_file(policy_path),
        "corpus_id": corpus.corpus_id,
        "corpus_version": corpus.version,
        "corpus_sha256": sha256_file(corpus_path),
        "freeze_sha256": sha256_file(freeze_path),
        "authorization": {
            "authorized_by": policy.authorized_by,
            "authorization_date": policy.authorization_date,
            "authorization_reason": policy.authorization_reason,
            "locked_use": policy.locked_use,
        },
        "thresholds": asdict(policy.thresholds),
        "metrics": {
            "development": _report_metrics(development),
            "validation": _report_metrics(validation),
            "locked_evaluation": _report_metrics(locked),
            "contradiction_pass_rate": readiness["contradiction_pass_rate"],
            "contradiction_measurements": readiness["contradiction_measurements"],
        },
        "split_threshold_checks": split_checks,
        "certification_decision": (
            "PASS_CONTRACT_CERTIFICATION" if passed else "FAIL_CONTRACT_CERTIFICATION"
        ),
        "interpretation_boundary": policy.interpretation_boundary,
        "checks": checks,
    }


def write_certification_report(report: dict[str, object], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_evidence_envelope(
    *,
    report_path: Path,
    validated_sha: str,
) -> dict[str, object]:
    report_value = json.loads(report_path.read_text(encoding="utf-8"))
    report = _mapping(report_value, "report")
    if report.get("status") != "PASS":
        raise ReasoningCertificationError("cannot build PASS evidence from non-PASS report")
    if report.get("validated_sha") != validated_sha:
        raise ReasoningCertificationError("report SHA does not match evidence SHA")
    return {
        "schema_version": "2.0",
        "step": 6,
        "status": "PASS",
        "validated_sha": validated_sha,
        "gate_kind": "certification",
        "evidence_kind": "reasoning_certification",
        "artifact_path": report_path.as_posix(),
        "artifact_sha256": sha256_file(report_path),
        "critical_gates_passed": True,
    }
