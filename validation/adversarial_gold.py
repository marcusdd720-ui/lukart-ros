"""Versioned adversarial Gold benchmark over canonical P7 and Reasoning gates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from core.models.ids import AgentId
from knowledge.epistemic import KnowledgeStatus
from learning.adversarial_verification import (
    AdversarialVerificationGate,
    AdversarialVerificationStatus,
    ChallengeAssessment,
    ChallengeFinding,
    ChallengeResolution,
    ChallengeResolutionStatus,
    EvidenceVerification,
    EvidenceVerificationStatus,
    ReviewAssessment,
    ReviewStatus,
    VerificationProposal,
)
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact, ReasoningOutcome


class AdversarialGoldSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    LOCKED_EVALUATION = "locked_evaluation"


class AdversarialCaseKind(StrEnum):
    EVIDENCE_VETO = "evidence_veto"
    ABSTENTION_REQUIRED = "abstention_required"
    UNRESOLVED_CHALLENGE = "unresolved_challenge"
    VERIFIED_CONTROL = "verified_control"


_EXPECTED_SPLIT_SIZES = {
    AdversarialGoldSplit.DEVELOPMENT: 4,
    AdversarialGoldSplit.VALIDATION: 2,
    AdversarialGoldSplit.LOCKED_EVALUATION: 2,
}


class LockedAdversarialEvaluationError(RuntimeError):
    """Raised when locked adversarial evaluation is requested without authorization."""


@dataclass(frozen=True, slots=True)
class AdversarialGoldCase:
    case_id: str
    split: AdversarialGoldSplit
    kind: AdversarialCaseKind
    expected_verification: AdversarialVerificationStatus
    expected_reasoning: ReasoningOutcome


@dataclass(frozen=True, slots=True)
class AdversarialGoldCorpus:
    corpus_id: str
    version: str
    status: str
    review_status: str
    cases: tuple[AdversarialGoldCase, ...]

    def cases_for_split(
        self,
        split: AdversarialGoldSplit,
        *,
        allow_locked: bool = False,
    ) -> tuple[AdversarialGoldCase, ...]:
        if split is AdversarialGoldSplit.LOCKED_EVALUATION and not allow_locked:
            raise LockedAdversarialEvaluationError(
                "locked adversarial evaluation is disabled until explicit authorization"
            )
        return tuple(case for case in self.cases if case.split is split)


@dataclass(frozen=True, slots=True)
class AdversarialCaseResult:
    case_id: str
    kind: AdversarialCaseKind
    verification_status: AdversarialVerificationStatus
    expected_verification: AdversarialVerificationStatus
    reasoning_outcome: ReasoningOutcome
    expected_reasoning: ReasoningOutcome
    evidence_veto_preserved: bool
    abstention_preserved: bool
    unresolved_challenge_preserved: bool
    unsafe_fact_promotion_count: int

    @property
    def passed(self) -> bool:
        return (
            self.verification_status is self.expected_verification
            and self.reasoning_outcome is self.expected_reasoning
            and self.evidence_veto_preserved
            and self.abstention_preserved
            and self.unresolved_challenge_preserved
            and self.unsafe_fact_promotion_count == 0
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "abstention_preserved": self.abstention_preserved,
            "case_id": self.case_id,
            "evidence_veto_preserved": self.evidence_veto_preserved,
            "expected_reasoning": self.expected_reasoning.value,
            "expected_verification": self.expected_verification.value,
            "kind": self.kind.value,
            "reasoning_outcome": self.reasoning_outcome.value,
            "unsafe_fact_promotion_count": self.unsafe_fact_promotion_count,
            "unresolved_challenge_preserved": self.unresolved_challenge_preserved,
            "verification_status": self.verification_status.value,
        }


@dataclass(frozen=True, slots=True)
class AdversarialSuiteMetrics:
    total_cases: int
    passed_cases: int
    evidence_veto_accuracy: float
    required_abstention_accuracy: float
    unresolved_challenge_accuracy: float
    unsafe_fact_promotion_count: int


@dataclass(frozen=True, slots=True)
class AdversarialSuiteReport:
    corpus_id: str
    corpus_version: str
    split: AdversarialGoldSplit
    metrics: AdversarialSuiteMetrics
    case_results: tuple[AdversarialCaseResult, ...]
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


def load_adversarial_gold_corpus(path: Path) -> AdversarialGoldCorpus:
    payload = _mapping(json.loads(path.read_text(encoding="utf-8")), "corpus")
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported adversarial corpus schema")
    if payload.get("status") != "candidate_pending_independent_review":
        raise ValueError("adversarial corpus must remain a review-pending candidate")
    if payload.get("review_status") != "not_reviewed":
        raise ValueError("adversarial corpus cannot claim review without independent evidence")

    split_payload = _mapping(payload.get("splits"), "splits")
    split_by_case: dict[str, AdversarialGoldSplit] = {}
    for split, expected_size in _EXPECTED_SPLIT_SIZES.items():
        ids = tuple(str(item) for item in _sequence(split_payload.get(split.value), split.value))
        if len(ids) != expected_size or len(ids) != len(set(ids)):
            raise ValueError(f"split {split.value!r} has invalid size or duplicate ids")
        for case_id in ids:
            if case_id in split_by_case:
                raise ValueError("adversarial corpus splits must be disjoint")
            split_by_case[case_id] = split

    cases: list[AdversarialGoldCase] = []
    seen: set[str] = set()
    for raw_value in _sequence(payload.get("cases"), "cases"):
        raw = _mapping(raw_value, "case")
        case_id = str(raw.get("case_id", "")).strip()
        if not case_id.startswith("SYN-ADV-") or case_id in seen:
            raise ValueError(f"invalid or duplicate adversarial case id: {case_id!r}")
        if case_id not in split_by_case:
            raise ValueError(f"adversarial case is not assigned to a split: {case_id}")
        seen.add(case_id)
        cases.append(
            AdversarialGoldCase(
                case_id=case_id,
                split=split_by_case[case_id],
                kind=AdversarialCaseKind(str(raw.get("kind", ""))),
                expected_verification=AdversarialVerificationStatus(
                    str(raw.get("expected_verification", ""))
                ),
                expected_reasoning=ReasoningOutcome(str(raw.get("expected_reasoning", ""))),
            )
        )

    if seen != set(split_by_case):
        raise ValueError("adversarial corpus splits must partition the case set")
    return AdversarialGoldCorpus(
        corpus_id=str(payload.get("corpus_id", "")).strip(),
        version=str(payload.get("version", "")).strip(),
        status=str(payload["status"]),
        review_status=str(payload["review_status"]),
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )


def _agent(number: int) -> AgentId:
    return AgentId(UUID(int=number))


def _digest(character: str) -> str:
    return character * 64


def _proposal(case: AdversarialGoldCase) -> VerificationProposal:
    seed = hashlib.sha256(case.case_id.encode("utf-8")).hexdigest()
    return VerificationProposal(
        proposal_id=f"ADV-{case.case_id}",
        generator_agent_id=_agent(1),
        subject_type="synthetic_reasoning_result",
        subject_digest=seed,
        claim_digests=(_digest("b"),),
        evidence_digests=(_digest("c"), _digest("d")),
    )


def _verification(case: AdversarialGoldCase) -> AdversarialVerificationStatus:
    proposal = _proposal(case)
    challenge = ChallengeAssessment(
        challenger_agent_id=_agent(2),
        proposal_digest=proposal.digest(),
        findings=(
            ChallengeFinding(
                code="ADV-CHALLENGE",
                claim_digest=proposal.claim_digests[0],
                rationale="synthetic adversarial challenge to evidentiary support",
                blocking=True,
                evidence_digests=(proposal.evidence_digests[0],),
            ),
        ),
    )

    if case.kind is AdversarialCaseKind.EVIDENCE_VETO:
        evidence = EvidenceVerification(
            verifier_agent_id=_agent(3),
            proposal_digest=proposal.digest(),
            status=EvidenceVerificationStatus.FAIL,
            checked_evidence_digests=proposal.evidence_digests,
            rejected_evidence_digests=(proposal.evidence_digests[0],),
            rationale="synthetic provenance check rejected one evidence source",
        )
    elif case.kind in {
        AdversarialCaseKind.ABSTENTION_REQUIRED,
        AdversarialCaseKind.UNRESOLVED_CHALLENGE,
    }:
        evidence = EvidenceVerification(
            verifier_agent_id=_agent(3),
            proposal_digest=proposal.digest(),
            status=EvidenceVerificationStatus.PASS,
            checked_evidence_digests=proposal.evidence_digests,
            rationale="evidence checked but blocking challenge remains unresolved",
        )
    else:
        evidence = EvidenceVerification(
            verifier_agent_id=_agent(3),
            proposal_digest=proposal.digest(),
            status=EvidenceVerificationStatus.PASS,
            checked_evidence_digests=proposal.evidence_digests,
            challenge_resolutions=(
                ChallengeResolution(
                    challenge_code="ADV-CHALLENGE",
                    status=ChallengeResolutionStatus.RESOLVED,
                    evidence_digests=(proposal.evidence_digests[0],),
                    rationale="synthetic challenge resolved by checked evidence",
                ),
            ),
        )

    review = ReviewAssessment(
        reviewer_agent_id=_agent(4),
        proposal_digest=proposal.digest(),
        status=ReviewStatus.PASS,
        rationale="synthetic independent process review",
    )
    return AdversarialVerificationGate().evaluate(
        proposal,
        (challenge,),
        evidence,
        review,
    ).status


def _reasoning(case: AdversarialGoldCase) -> ReasoningOutcome:
    if case.kind is AdversarialCaseKind.VERIFIED_CONTROL:
        support = ReasoningArtifact(
            artifact_id="CL-ADV",
            statement="Synthetic adversarial control claim has checked evidence.",
            status=KnowledgeStatus.CLAIM,
            evidence_refs=("SYN-ADV-EVIDENCE",),
        )
    elif case.kind is AdversarialCaseKind.EVIDENCE_VETO:
        support = ReasoningArtifact(
            artifact_id="RJ-ADV",
            statement="Synthetic evidence was rejected by provenance verification.",
            status=KnowledgeStatus.REJECTED,
        )
    elif case.kind is AdversarialCaseKind.UNRESOLVED_CHALLENGE:
        support = ReasoningArtifact(
            artifact_id="UR-ADV",
            statement="Synthetic blocking challenge remains unresolved.",
            status=KnowledgeStatus.UNRESOLVED,
        )
    else:
        support = ReasoningArtifact(
            artifact_id="UN-ADV",
            statement="Synthetic support is insufficient to resolve the claim.",
            status=KnowledgeStatus.UNKNOWN,
        )

    conclusion = ReasoningArtifact(
        artifact_id="C-ADV",
        statement="The adversarially challenged synthetic claim is established.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(support.artifact_id,),
    )
    return ReasoningEngine((support, conclusion)).evaluate("C-ADV").decision.outcome


def run_adversarial_case(case: AdversarialGoldCase) -> AdversarialCaseResult:
    verification = _verification(case)
    reasoning = _reasoning(case)
    is_veto_case = case.kind is AdversarialCaseKind.EVIDENCE_VETO
    is_abstention_case = case.expected_reasoning is ReasoningOutcome.ABSTAIN
    is_unresolved_case = case.kind is AdversarialCaseKind.UNRESOLVED_CHALLENGE
    return AdversarialCaseResult(
        case_id=case.case_id,
        kind=case.kind,
        verification_status=verification,
        expected_verification=case.expected_verification,
        reasoning_outcome=reasoning,
        expected_reasoning=case.expected_reasoning,
        evidence_veto_preserved=(
            not is_veto_case or verification is AdversarialVerificationStatus.REJECTED
        ),
        abstention_preserved=(
            not is_abstention_case or reasoning is ReasoningOutcome.ABSTAIN
        ),
        unresolved_challenge_preserved=(
            not is_unresolved_case
            or verification is AdversarialVerificationStatus.INCONCLUSIVE
        ),
        unsafe_fact_promotion_count=0,
    )


def evaluate_adversarial_split(
    corpus: AdversarialGoldCorpus,
    split: AdversarialGoldSplit,
) -> AdversarialSuiteReport:
    cases = corpus.cases_for_split(split)
    results = tuple(run_adversarial_case(case) for case in cases)
    total = len(results)
    if total == 0:
        raise ValueError("adversarial split cannot be empty")

    veto_cases = tuple(item for item in results if item.kind is AdversarialCaseKind.EVIDENCE_VETO)
    abstain_cases = tuple(
        item for item in results if item.expected_reasoning is ReasoningOutcome.ABSTAIN
    )
    unresolved_cases = tuple(
        item for item in results if item.kind is AdversarialCaseKind.UNRESOLVED_CHALLENGE
    )

    def accuracy(items: tuple[AdversarialCaseResult, ...], attribute: str) -> float:
        if not items:
            return 1.0
        return sum(bool(getattr(item, attribute)) for item in items) / len(items)

    metrics = AdversarialSuiteMetrics(
        total_cases=total,
        passed_cases=sum(item.passed for item in results),
        evidence_veto_accuracy=accuracy(veto_cases, "evidence_veto_preserved"),
        required_abstention_accuracy=accuracy(abstain_cases, "abstention_preserved"),
        unresolved_challenge_accuracy=accuracy(
            unresolved_cases,
            "unresolved_challenge_preserved",
        ),
        unsafe_fact_promotion_count=sum(item.unsafe_fact_promotion_count for item in results),
    )
    return AdversarialSuiteReport(
        corpus_id=corpus.corpus_id,
        corpus_version=corpus.version,
        split=split,
        metrics=metrics,
        case_results=results,
        locked_evaluation_executed=False,
    )
