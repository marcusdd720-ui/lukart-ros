"""Controlled self-learning closure over existing P4-P6 evidence gates.

P7 does not mutate Product state. It verifies that an independently confirmed
measured failure became the same P4 LearningCandidate, bounded experiment,
measured promotion decision, and P6 fresh-SHA readiness artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from learning.adversarial_verification import (
    AdversarialVerificationDecision,
    AdversarialVerificationStatus,
)
from learning.experiment import ExperimentContract
from learning.models import LearningCandidate, MeasuredFailure
from learning.promotion import PromotionDecision, PromotionStatus
from learning.semantic_self_healing import (
    RepairReadinessDecision,
    RepairReadinessStatus,
)


class SelfLearningCycleStatus(StrEnum):
    READY_FOR_EXISTING_RELEASE_PATH = "ready_for_existing_release_path"
    SUSPENDED = "suspended"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class SelfLearningCycleDecision:
    """Governance artifact only; never code/model/prompt mutation authority."""

    status: SelfLearningCycleStatus
    reason: str
    failure_digest: str
    verification_digest: str
    candidate_digest: str
    experiment_digest: str
    validation_evidence_digest: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_digest": self.candidate_digest,
            "experiment_digest": self.experiment_digest,
            "failure_digest": self.failure_digest,
            "reason": self.reason,
            "status": self.status.value,
            "validation_evidence_digest": self.validation_evidence_digest,
            "verification_digest": self.verification_digest,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ControlledSelfLearningGate:
    """Close one measured cycle without mutation or deployment authority."""

    def evaluate(
        self,
        failure: MeasuredFailure,
        verification: AdversarialVerificationDecision,
        candidate: LearningCandidate,
        experiment: ExperimentContract,
        promotion: PromotionDecision,
        readiness: RepairReadinessDecision,
    ) -> SelfLearningCycleDecision:
        failure_digest = failure.digest()
        verification_digest = verification.digest()
        candidate_digest = candidate.digest()
        experiment_digest = experiment.digest()

        def decide(
            status: SelfLearningCycleStatus,
            reason: str,
        ) -> SelfLearningCycleDecision:
            return SelfLearningCycleDecision(
                status=status,
                reason=reason,
                failure_digest=failure_digest,
                verification_digest=verification_digest,
                candidate_digest=candidate_digest,
                experiment_digest=experiment_digest,
                validation_evidence_digest=readiness.validation_evidence_digest,
            )

        if verification.proposal_subject_type != "measured_failure":
            return decide(
                SelfLearningCycleStatus.REJECTED,
                (
                    "self-learning requires adversarial verification of a "
                    "measured_failure subject"
                ),
            )
        if verification.proposal_subject_digest != failure_digest:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "adversarial verification is not bound to this measured failure",
            )
        if verification.status is AdversarialVerificationStatus.REJECTED:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "adversarial verification rejected the learning trigger",
            )
        if verification.status is AdversarialVerificationStatus.INCONCLUSIVE:
            return decide(
                SelfLearningCycleStatus.INCONCLUSIVE,
                (
                    "adversarial verification did not establish a trustworthy "
                    "learning trigger"
                ),
            )
        if candidate.source_failure_digest != failure_digest:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "learning candidate is not bound to this measured failure",
            )
        if experiment.candidate_digest != candidate_digest:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "experiment is not bound to this learning candidate",
            )
        if experiment.target_component != candidate.target_component:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "experiment target does not match the learning candidate",
            )
        if promotion.contract_digest != experiment_digest:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "promotion decision is not bound to this experiment",
            )

        regression = any(
            delta.signed_improvement < -delta.allowed_regression
            for delta in promotion.deltas
        )
        if regression:
            return decide(
                SelfLearningCycleStatus.SUSPENDED,
                "measured regression exceeded a P4 guardrail; candidate is suspended",
            )
        if promotion.status is PromotionStatus.REJECTED:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "P4 PromotionGate rejected the candidate",
            )
        if promotion.status is PromotionStatus.INCONCLUSIVE:
            return decide(
                SelfLearningCycleStatus.INCONCLUSIVE,
                "P4 experiment produced no sufficient measured improvement",
            )
        if readiness.candidate_digest != candidate_digest:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "P6 readiness is not bound to this learning candidate",
            )
        if readiness.status is not RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION:
            return decide(
                SelfLearningCycleStatus.REJECTED,
                "P6 fresh-SHA semantic self-healing gate did not accept the repair",
            )

        return decide(
            SelfLearningCycleStatus.READY_FOR_EXISTING_RELEASE_PATH,
            (
                "independently verified measured failure completed P4 experiment "
                "and P6 fresh-SHA gates; the candidate may continue only through "
                "the existing controlled release path"
            ),
        )
