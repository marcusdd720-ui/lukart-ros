"""Minimal deterministic reasoning engine with calibrated abstention."""

from __future__ import annotations

import hashlib

from knowledge.epistemic import KnowledgeStatus
from reasoning.models import (
    OpenQuestion,
    ReasoningArtifact,
    ReasoningDecision,
    ReasoningOutcome,
    ReasoningRunResult,
)
from reasoning.open_questions import OpenQuestionsLedger
from reasoning.validation import validate_reasoning_graph

_BLOCKING_STATES = frozenset(
    {
        KnowledgeStatus.UNKNOWN,
        KnowledgeStatus.UNRESOLVED,
        KnowledgeStatus.REJECTED,
    }
)


class ReasoningEngine:
    """Evaluate predeclared reasoning artifacts; never invent missing conclusions."""

    def __init__(self, artifacts: tuple[ReasoningArtifact, ...]) -> None:
        self._artifacts = artifacts
        self._by_id = {artifact.artifact_id: artifact for artifact in artifacts}

    def evaluate(self, conclusion_id: str) -> ReasoningRunResult:
        conclusion_id = conclusion_id.strip()
        validation = validate_reasoning_graph(self._artifacts)
        ledger = OpenQuestionsLedger.from_validation_issues(validation.issues)

        conclusion = self._by_id.get(conclusion_id)
        if conclusion is None:
            self._add_question(
                ledger,
                seed=f"missing-conclusion|{conclusion_id}",
                question="Which explicit conclusion artifact should be evaluated?",
                reason=f"conclusion artifact not found: {conclusion_id}",
            )
            return self._abstain(ledger, f"conclusion artifact not found: {conclusion_id}")

        if conclusion.status is not KnowledgeStatus.CONCLUSION:
            self._add_question(
                ledger,
                seed=f"wrong-status|{conclusion_id}|{conclusion.status.value}",
                question="Should this artifact be promoted to CONCLUSION under epistemic policy?",
                reason=f"artifact status is {conclusion.status.value}, not CONCLUSION",
                related=(conclusion_id,),
            )
            return self._abstain(
                ledger,
                f"artifact {conclusion_id} is not a CONCLUSION",
            )

        lineage_ids = self._lineage_ids(conclusion_id)
        blocking = sorted(
            artifact_id
            for artifact_id in lineage_ids
            if self._by_id[artifact_id].status in _BLOCKING_STATES
        )
        for artifact_id in blocking:
            artifact = self._by_id[artifact_id]
            self._add_question(
                ledger,
                seed=f"blocking|{artifact_id}|{artifact.status.value}",
                question=f"What evidence resolves artifact {artifact_id}?",
                reason=f"support lineage contains {artifact.status.value}",
                related=(artifact_id, conclusion_id),
            )

        relevant_issues = tuple(
            issue
            for issue in validation.issues
            if issue.artifact_id is None or issue.artifact_id in lineage_ids
        )
        if relevant_issues or blocking:
            return self._abstain(
                ledger,
                "reasoning support is incomplete, invalid, or unresolved",
            )

        decision = ReasoningDecision(
            outcome=ReasoningOutcome.CONCLUDE,
            artifact_id=conclusion_id,
            reason="conclusion has a valid evidence-backed support lineage",
        )
        return ReasoningRunResult(
            artifacts=self._artifacts,
            open_questions=ledger.questions(),
            decision=decision,
        )

    def _abstain(self, ledger: OpenQuestionsLedger, reason: str) -> ReasoningRunResult:
        questions = ledger.questions()
        decision = ReasoningDecision(
            outcome=ReasoningOutcome.ABSTAIN,
            reason=reason,
            open_question_ids=tuple(question.question_id for question in questions),
        )
        return ReasoningRunResult(
            artifacts=self._artifacts,
            open_questions=questions,
            decision=decision,
        )

    def _lineage_ids(self, artifact_id: str) -> set[str]:
        found: set[str] = set()
        pending = [artifact_id]
        while pending:
            current = pending.pop()
            if current in found or current not in self._by_id:
                continue
            found.add(current)
            pending.extend(self._by_id[current].support_ids)
        return found

    @staticmethod
    def _add_question(
        ledger: OpenQuestionsLedger,
        *,
        seed: str,
        question: str,
        reason: str,
        related: tuple[str, ...] = (),
    ) -> None:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        ledger.add(
            OpenQuestion(
                question_id=f"OQ-{digest}",
                question=question,
                reason=reason,
                related_artifact_ids=related,
            )
        )
