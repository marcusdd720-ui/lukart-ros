"""Open Questions Ledger for explicit unknowns and unresolved reasoning gaps."""

from __future__ import annotations

import hashlib

from reasoning.models import OpenQuestion
from reasoning.validation import ReasoningValidationIssue


class OpenQuestionsLedger:
    """Deterministic collection of unresolved information needs."""

    def __init__(self, questions: tuple[OpenQuestion, ...] = ()) -> None:
        self._questions: dict[str, OpenQuestion] = {}
        for question in questions:
            self.add(question)

    def add(self, question: OpenQuestion) -> None:
        existing = self._questions.get(question.question_id)
        if existing is not None and existing != question:
            raise ValueError(f"conflicting open question id: {question.question_id}")
        self._questions[question.question_id] = question

    def questions(self) -> tuple[OpenQuestion, ...]:
        return tuple(self._questions[key] for key in sorted(self._questions))

    @classmethod
    def from_validation_issues(
        cls,
        issues: tuple[ReasoningValidationIssue, ...],
    ) -> OpenQuestionsLedger:
        ledger = cls()
        for issue in issues:
            related = (issue.artifact_id,) if issue.artifact_id else ()
            seed = f"{issue.code}|{issue.artifact_id or ''}|{issue.message}"
            digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
            ledger.add(
                OpenQuestion(
                    question_id=f"OQ-{digest}",
                    question=f"What evidence or reasoning is required to resolve {issue.code}?",
                    reason=issue.message,
                    related_artifact_ids=related,
                )
            )
        return ledger
