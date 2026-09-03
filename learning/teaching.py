"""Controlled agent teaching and distillation manifests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from string import hexdigits

from agents.certification import (
    AgentCertificationReport,
    AgentCertificationStatus,
    contract_sha256,
)
from agents.contract import AgentContract
from learning.experiment import ExperimentContract
from learning.models import ChangeKind, LearningCandidate, MeasuredFailure
from learning.promotion import PromotionDecision, PromotionStatus
from validation.independent_evaluation import ReviewOutcome

_ALLOWED_TEACHING_SPLITS = frozenset({"development", "validation"})
_ALLOWED_DISTILLATION_KINDS = frozenset(
    {
        ChangeKind.PROMPT,
        ChangeKind.RETRIEVAL,
        ChangeKind.RULE,
        ChangeKind.MODEL,
    }
)
_FORBIDDEN_REVIEWER_IDS = frozenset({"system", "automated", "factory"})
_HEX_DIGITS = frozenset(hexdigits.lower())
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _required_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be blank")
    return normalized


def _sha256_digest(name: str, value: str) -> str:
    digest = _required_text(name, value).lower()
    if len(digest) != 64 or any(character not in _HEX_DIGITS for character in digest):
        raise ValueError(f"{name} must be a SHA-256 digest")
    return digest


def _digest_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class TeachingExampleKind(StrEnum):
    GOLD = "gold"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class TeachingExample:
    """Digest-bound example manifest; raw case payload is intentionally excluded."""

    example_id: str
    kind: TeachingExampleKind
    source_corpus_id: str
    source_corpus_version: str
    split: str
    source_ref: str
    source_digest: str
    input_digest: str
    expected_output_digest: str
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "example_id",
            "source_corpus_id",
            "source_corpus_version",
            "source_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(field_name, str(getattr(self, field_name))),
            )
        split = _required_text("split", self.split)
        if split not in _ALLOWED_TEACHING_SPLITS:
            raise ValueError(f"unsupported teaching split: {split}")
        object.__setattr__(self, "split", split)
        for field_name in ("source_digest", "input_digest", "expected_output_digest"):
            object.__setattr__(
                self,
                field_name,
                _sha256_digest(field_name, str(getattr(self, field_name))),
            )
        evidence = tuple(
            _sha256_digest("evidence_digest", digest) for digest in self.evidence_digests
        )
        if not evidence:
            raise ValueError("teaching example requires evidence digests")
        if len(evidence) != len(set(evidence)):
            raise ValueError("teaching example evidence digests must be unique")
        object.__setattr__(self, "evidence_digests", evidence)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "evidence_digests": list(self.evidence_digests),
            "example_id": self.example_id,
            "expected_output_digest": self.expected_output_digest,
            "input_digest": self.input_digest,
            "kind": self.kind.value,
            "source_corpus_id": self.source_corpus_id,
            "source_corpus_version": self.source_corpus_version,
            "source_digest": self.source_digest,
            "source_ref": self.source_ref,
            "split": self.split,
        }

    def digest(self) -> str:
        return _digest_payload(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class TeachingApproval:
    """Independent approval bound to one exact teaching example."""

    example_digest: str
    reviewer_id: str
    outcome: ReviewOutcome
    rationale: str
    evidence_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "example_digest",
            _sha256_digest("example_digest", self.example_digest),
        )
        reviewer_id = _required_text("reviewer_id", self.reviewer_id)
        if reviewer_id.lower() in _FORBIDDEN_REVIEWER_IDS:
            raise ValueError("reviewer_id must identify an independent reviewer")
        object.__setattr__(self, "reviewer_id", reviewer_id)
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))
        object.__setattr__(
            self,
            "evidence_ref",
            _required_text("evidence_ref", self.evidence_ref),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "evidence_ref": self.evidence_ref,
            "example_digest": self.example_digest,
            "outcome": self.outcome.value,
            "rationale": self.rationale,
            "reviewer_id": self.reviewer_id,
        }

    def digest(self) -> str:
        return _digest_payload(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class AgentTeachingPackage:
    """Versioned teaching manifest. It has no authority to mutate an agent."""

    package_id: str
    package_version: str
    target_agent_id: str
    target_agent_name: str
    target_agent_version: str
    target_contract_digest: str
    target_component: str
    change_kind: ChangeKind
    candidate_digest: str
    experiment_contract_digest: str
    promotion_decision_digest: str
    teaching_instruction: str
    example_digests: tuple[str, ...]
    approval_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "package_id",
            "target_agent_id",
            "target_agent_name",
            "target_agent_version",
            "target_component",
            "teaching_instruction",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(field_name, str(getattr(self, field_name))),
            )
        package_version = _required_text("package_version", self.package_version)
        if not _SEMVER_RE.fullmatch(package_version):
            raise ValueError("package_version must use MAJOR.MINOR.PATCH semver")
        object.__setattr__(self, "package_version", package_version)
        for field_name in (
            "target_contract_digest",
            "candidate_digest",
            "experiment_contract_digest",
            "promotion_decision_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _sha256_digest(field_name, str(getattr(self, field_name))),
            )
        if self.change_kind not in _ALLOWED_DISTILLATION_KINDS:
            raise ValueError(
                f"unsupported P5 distillation change kind: {self.change_kind.value}"
            )
        examples = tuple(
            _sha256_digest("example_digest", digest) for digest in self.example_digests
        )
        approvals = tuple(
            _sha256_digest("approval_digest", digest) for digest in self.approval_digests
        )
        if not examples:
            raise ValueError("teaching package requires examples")
        if len(examples) != len(set(examples)):
            raise ValueError("teaching package example digests must be unique")
        if len(approvals) != len(set(approvals)):
            raise ValueError("teaching package approval digests must be unique")
        if len(examples) != len(approvals):
            raise ValueError("every teaching example requires exactly one approval")
        object.__setattr__(self, "example_digests", examples)
        object.__setattr__(self, "approval_digests", approvals)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "approval_digests": list(self.approval_digests),
            "candidate_digest": self.candidate_digest,
            "change_kind": self.change_kind.value,
            "example_digests": list(self.example_digests),
            "experiment_contract_digest": self.experiment_contract_digest,
            "package_id": self.package_id,
            "package_version": self.package_version,
            "promotion_decision_digest": self.promotion_decision_digest,
            "target_agent_id": self.target_agent_id,
            "target_agent_name": self.target_agent_name,
            "target_agent_version": self.target_agent_version,
            "target_component": self.target_component,
            "target_contract_digest": self.target_contract_digest,
            "teaching_instruction": self.teaching_instruction,
        }

    def digest(self) -> str:
        return _digest_payload(self.canonical_dict())


class TeachingReleaseStatus(StrEnum):
    PENDING_RECERTIFICATION = "pending_recertification"
    ELIGIBLE_FOR_RELEASE = "eligible_for_release"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TeachingReleaseDecision:
    package_digest: str
    status: TeachingReleaseStatus
    reason: str
    certification_status: AgentCertificationStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "package_digest",
            _sha256_digest("package_digest", self.package_digest),
        )
        object.__setattr__(self, "reason", _required_text("reason", self.reason))


def promotion_decision_digest(decision: PromotionDecision) -> str:
    payload: dict[str, object] = {
        "contract_digest": decision.contract_digest,
        "deltas": [
            {
                "allowed_regression": delta.allowed_regression,
                "baseline": delta.baseline,
                "candidate": delta.candidate,
                "name": delta.name,
                "signed_improvement": delta.signed_improvement,
            }
            for delta in decision.deltas
        ],
        "reason": decision.reason,
        "status": decision.status.value,
    }
    return _digest_payload(payload)


def gold_teaching_example(
    *,
    example_id: str,
    corpus_id: str,
    corpus_version: str,
    split: str,
    source_ref: str,
    source_digest: str,
    input_digest: str,
    expected_output_digest: str,
    evidence_digests: tuple[str, ...],
) -> TeachingExample:
    return TeachingExample(
        example_id=example_id,
        kind=TeachingExampleKind.GOLD,
        source_corpus_id=corpus_id,
        source_corpus_version=corpus_version,
        split=split,
        source_ref=source_ref,
        source_digest=source_digest,
        input_digest=input_digest,
        expected_output_digest=expected_output_digest,
        evidence_digests=evidence_digests,
    )


def failure_teaching_example(
    failure: MeasuredFailure,
    *,
    input_digest: str,
    expected_output_digest: str,
    evidence_digests: tuple[str, ...],
) -> TeachingExample:
    return TeachingExample(
        example_id=f"FAILURE-{failure.failure_id}",
        kind=TeachingExampleKind.FAILURE,
        source_corpus_id=failure.corpus_id,
        source_corpus_version=failure.corpus_version,
        split=failure.split,
        source_ref=f"measured-failure:{failure.failure_id}",
        source_digest=failure.digest(),
        input_digest=input_digest,
        expected_output_digest=expected_output_digest,
        evidence_digests=evidence_digests,
    )


def distill_agent_teaching_package(
    candidate: LearningCandidate,
    experiment_contract: ExperimentContract,
    promotion_decision: PromotionDecision,
    target_contract: AgentContract,
    *,
    package_version: str,
    teaching_instruction: str,
    examples: tuple[TeachingExample, ...],
    approvals: tuple[TeachingApproval, ...],
) -> AgentTeachingPackage:
    """Create a manifest only after P4 and independent-example gates are satisfied."""

    candidate_digest = candidate.digest()
    if candidate.change_kind not in _ALLOWED_DISTILLATION_KINDS:
        raise ValueError(f"P5 cannot distill change kind: {candidate.change_kind.value}")
    if experiment_contract.candidate_digest != candidate_digest:
        raise ValueError("experiment contract is not bound to this learning candidate")
    if experiment_contract.target_component != candidate.target_component:
        raise ValueError("experiment target component does not match learning candidate")
    contract_digest = experiment_contract.digest()
    if promotion_decision.contract_digest != contract_digest:
        raise ValueError("promotion decision is not bound to this experiment contract")
    if promotion_decision.status is not PromotionStatus.ELIGIBLE_FOR_PROMOTION:
        raise ValueError("P5 requires an ELIGIBLE_FOR_PROMOTION decision")
    if not examples:
        raise ValueError("P5 distillation requires at least one teaching example")

    example_digests = tuple(example.digest() for example in examples)
    if len(example_digests) != len(set(example_digests)):
        raise ValueError("teaching examples must be unique")

    approval_by_example: dict[str, TeachingApproval] = {}
    for approval in approvals:
        if approval.example_digest in approval_by_example:
            raise ValueError("each teaching example must have exactly one approval")
        approval_by_example[approval.example_digest] = approval

    if set(approval_by_example) != set(example_digests):
        raise ValueError("teaching approvals must exactly cover teaching examples")
    ordered_approvals = tuple(approval_by_example[digest] for digest in example_digests)
    if any(approval.outcome is not ReviewOutcome.PASS for approval in ordered_approvals):
        raise ValueError("every teaching example requires independent PASS approval")

    target_digest = contract_sha256(target_contract)
    decision_digest = promotion_decision_digest(promotion_decision)
    seed = "|".join(
        (
            candidate_digest,
            contract_digest,
            decision_digest,
            target_digest,
            package_version.strip(),
            *example_digests,
        )
    )
    package_id = f"TP-{hashlib.sha256(seed.encode()).hexdigest()[:12].upper()}"

    return AgentTeachingPackage(
        package_id=package_id,
        package_version=package_version,
        target_agent_id=str(target_contract.agent_id),
        target_agent_name=target_contract.name,
        target_agent_version=target_contract.version,
        target_contract_digest=target_digest,
        target_component=candidate.target_component,
        change_kind=candidate.change_kind,
        candidate_digest=candidate_digest,
        experiment_contract_digest=contract_digest,
        promotion_decision_digest=decision_digest,
        teaching_instruction=teaching_instruction,
        example_digests=example_digests,
        approval_digests=tuple(approval.digest() for approval in ordered_approvals),
    )


class AgentTeachingReleaseGate:
    """Require recertification of the exact taught agent contract before release."""

    def evaluate(
        self,
        package: AgentTeachingPackage,
        certification: AgentCertificationReport,
    ) -> TeachingReleaseDecision:
        package_digest = package.digest()
        if certification.agent_name != package.target_agent_name:
            return self._rejected(package_digest, certification, "agent name mismatch")
        if certification.agent_version != package.target_agent_version:
            return self._rejected(package_digest, certification, "agent version mismatch")
        if certification.contract_sha256 != package.target_contract_digest:
            return self._rejected(
                package_digest,
                certification,
                "agent contract digest mismatch",
            )
        if certification.status is AgentCertificationStatus.REJECTED:
            return self._rejected(
                package_digest,
                certification,
                "agent recertification rejected",
            )
        if certification.status is AgentCertificationStatus.CERTIFIED:
            return TeachingReleaseDecision(
                package_digest=package_digest,
                status=TeachingReleaseStatus.ELIGIBLE_FOR_RELEASE,
                reason="exact taught agent contract is recertified",
                certification_status=certification.status,
            )
        return TeachingReleaseDecision(
            package_digest=package_digest,
            status=TeachingReleaseStatus.PENDING_RECERTIFICATION,
            reason="exact taught agent contract is not yet certified",
            certification_status=certification.status,
        )

    @staticmethod
    def _rejected(
        package_digest: str,
        certification: AgentCertificationReport,
        reason: str,
    ) -> TeachingReleaseDecision:
        return TeachingReleaseDecision(
            package_digest=package_digest,
            status=TeachingReleaseStatus.REJECTED,
            reason=reason,
            certification_status=certification.status,
        )