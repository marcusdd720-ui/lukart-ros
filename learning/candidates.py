"""Controlled creation of learning candidates from measured failures."""

from __future__ import annotations

import hashlib

from learning.models import ChangeKind, LearningCandidate, MeasuredFailure


def candidate_from_failure(
    failure: MeasuredFailure,
    *,
    target_component: str,
    change_kind: ChangeKind,
    hypothesis: str,
    success_criteria: tuple[str, ...],
) -> LearningCandidate:
    """Create an improvement hypothesis without changing trusted Product state."""

    target = target_component.strip()
    hypothesis_text = hypothesis.strip()
    if not target or not hypothesis_text:
        raise ValueError("target component and hypothesis are required")

    seed = f"{failure.digest()}:{target}:{change_kind.value}:{hypothesis_text}".encode("utf-8")
    candidate_id = f"LC-{hashlib.sha256(seed).hexdigest()[:16]}"
    problem_statement = (
        f"Measured {failure.code} on {failure.case_id}: "
        f"expected {failure.expected!r}, observed {failure.actual!r}."
    )
    return LearningCandidate(
        candidate_id=candidate_id,
        source_failure_digest=failure.digest(),
        target_component=target,
        change_kind=change_kind,
        problem_statement=problem_statement,
        hypothesis=hypothesis_text,
        success_criteria=success_criteria,
    )
