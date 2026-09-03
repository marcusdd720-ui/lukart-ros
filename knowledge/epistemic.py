"""Formal epistemic status machine for controlled knowledge promotion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KnowledgeStatus(StrEnum):
    FACT = "FACT"
    CLAIM = "CLAIM"
    INTERPRETATION = "INTERPRETATION"
    HYPOTHESIS = "HYPOTHESIS"
    CONCLUSION = "CONCLUSION"
    RECOMMENDATION = "RECOMMENDATION"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class EpistemicTransitionRequest:
    source: KnowledgeStatus
    target: KnowledgeStatus
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class EpistemicTransitionDecision:
    allowed: bool
    source: KnowledgeStatus
    target: KnowledgeStatus
    reason: str


class EpistemicTransitionError(ValueError):
    """Raised when a caller requests a forbidden epistemic promotion."""


class EpistemicStatusMachine:
    """Fail-closed transition policy for knowledge states.

    The machine does not decide whether evidence is true. It only enforces the
    minimum authority required to change epistemic state.
    """

    _allowed_without_new_evidence = frozenset(
        {
            (KnowledgeStatus.CLAIM, KnowledgeStatus.INTERPRETATION),
            (KnowledgeStatus.CLAIM, KnowledgeStatus.HYPOTHESIS),
            (KnowledgeStatus.INTERPRETATION, KnowledgeStatus.HYPOTHESIS),
            (KnowledgeStatus.HYPOTHESIS, KnowledgeStatus.CONCLUSION),
            (KnowledgeStatus.CONCLUSION, KnowledgeStatus.RECOMMENDATION),
            (KnowledgeStatus.UNKNOWN, KnowledgeStatus.UNRESOLVED),
            (KnowledgeStatus.UNRESOLVED, KnowledgeStatus.UNKNOWN),
        }
    )

    _requires_evidence = frozenset(
        {
            (KnowledgeStatus.CLAIM, KnowledgeStatus.FACT),
            (KnowledgeStatus.INTERPRETATION, KnowledgeStatus.FACT),
            (KnowledgeStatus.HYPOTHESIS, KnowledgeStatus.FACT),
            (KnowledgeStatus.UNRESOLVED, KnowledgeStatus.FACT),
            (KnowledgeStatus.UNKNOWN, KnowledgeStatus.FACT),
        }
    )

    def decide(self, request: EpistemicTransitionRequest) -> EpistemicTransitionDecision:
        if request.source is request.target:
            return EpistemicTransitionDecision(
                allowed=True,
                source=request.source,
                target=request.target,
                reason="status unchanged",
            )

        transition = (request.source, request.target)
        if request.target is KnowledgeStatus.REJECTED:
            if not request.rationale.strip():
                return self._deny(request, "rejection requires rationale")
            return self._allow(request, "rejection recorded with rationale")

        if transition in self._requires_evidence:
            if not self._has_evidence(request.evidence_refs):
                return self._deny(request, "promotion to FACT requires new evidence")
            return self._allow(request, "evidence-backed promotion to FACT")

        if request.source is KnowledgeStatus.FACT and request.target in {
            KnowledgeStatus.INTERPRETATION,
            KnowledgeStatus.HYPOTHESIS,
            KnowledgeStatus.CONCLUSION,
            KnowledgeStatus.RECOMMENDATION,
        }:
            return self._deny(request, "FACT cannot be silently relabeled as derived reasoning")

        if transition in self._allowed_without_new_evidence:
            return self._allow(request, "allowed derived-state transition")

        return self._deny(request, "transition is not authorized by epistemic policy")

    def require(self, request: EpistemicTransitionRequest) -> EpistemicTransitionDecision:
        decision = self.decide(request)
        if not decision.allowed:
            raise EpistemicTransitionError(decision.reason)
        return decision

    @staticmethod
    def _has_evidence(refs: tuple[str, ...]) -> bool:
        return bool(refs) and all(ref.strip() for ref in refs)

    @staticmethod
    def _allow(
        request: EpistemicTransitionRequest,
        reason: str,
    ) -> EpistemicTransitionDecision:
        return EpistemicTransitionDecision(True, request.source, request.target, reason)

    @staticmethod
    def _deny(
        request: EpistemicTransitionRequest,
        reason: str,
    ) -> EpistemicTransitionDecision:
        return EpistemicTransitionDecision(False, request.source, request.target, reason)
