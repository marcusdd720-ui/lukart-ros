from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.promotion import quorum_from_bundle
from core.night_shift.verification import (
    REQUIRED_VERIFICATION_GATES,
    VerificationBundle,
    VerificationEvidence,
    VerificationGate,
    load_verification_max_age_seconds,
)

SHA = "a" * 40
TASK = "b" * 64
BUILDER = "builder-a"
REVIEWER = "reviewer-b"
NOW = 20
MAX_AGE = 3600
PROFILE = Path("docs/execution_profiles/NIGHT_SHIFT_VERIFICATION_QUORUM_V1.yaml")


def _evidence(
    *,
    subject_sha: str = SHA,
    task_digest: str = TASK,
    failed_gate: VerificationGate | None = None,
) -> tuple[VerificationEvidence, ...]:
    return tuple(
        VerificationEvidence(
            gate=gate,
            passed=gate is not failed_gate,
            subject_sha=subject_sha,
            task_capsule_digest=task_digest,
            producer_identity=REVIEWER if gate is VerificationGate.INDEPENDENT_REVIEW else BUILDER,
            observed_at_epoch=10,
            evidence_digest="c" * 64,
            evidence_refs=(f"evidence:{gate.value}",),
        )
        for gate in REQUIRED_VERIFICATION_GATES
    )


def _bundle(**kwargs: object) -> VerificationBundle:
    return VerificationBundle(
        subject_sha=SHA,
        task_capsule_digest=TASK,
        builder_identity=BUILDER,
        reviewer_identity=REVIEWER,
        evidence=_evidence(),
        **kwargs,
    )


def test_complete_bundle_builds_evidence_bound_quorum() -> None:
    bundle = _bundle()
    quorum = quorum_from_bundle(
        bundle,
        now_epoch=NOW,
        max_evidence_age_seconds=MAX_AGE,
    )

    assert bundle.passed()
    assert quorum.passed()
    assert quorum.subject_sha == SHA
    assert quorum.task_capsule_digest == TASK
    assert quorum.evidence_digest == bundle.digest()
    assert quorum.builder_identity == BUILDER
    assert quorum.reviewer_identity == REVIEWER


def test_missing_gate_fails_closed() -> None:
    evidence = _evidence()[:-1]
    with pytest.raises(NightShiftContractError, match="evidence incomplete"):
        VerificationBundle(SHA, TASK, BUILDER, REVIEWER, evidence)


def test_duplicate_gate_fails_closed() -> None:
    evidence = _evidence()
    with pytest.raises(NightShiftContractError, match="duplicate verification evidence"):
        VerificationBundle(SHA, TASK, BUILDER, REVIEWER, evidence + (evidence[0],))


def test_mixed_subject_sha_fails_closed() -> None:
    evidence = list(_evidence())
    evidence[0] = replace(evidence[0], subject_sha="c" * 40)
    with pytest.raises(NightShiftContractError, match="subject SHA"):
        VerificationBundle(SHA, TASK, BUILDER, REVIEWER, tuple(evidence))


def test_mixed_task_capsule_fails_closed() -> None:
    evidence = list(_evidence())
    evidence[0] = replace(evidence[0], task_capsule_digest="d" * 64)
    with pytest.raises(NightShiftContractError, match="task capsule"):
        VerificationBundle(SHA, TASK, BUILDER, REVIEWER, tuple(evidence))


def test_independent_review_must_come_from_declared_reviewer() -> None:
    evidence = list(_evidence())
    index = next(
        i for i, item in enumerate(evidence)
        if item.gate is VerificationGate.INDEPENDENT_REVIEW
    )
    evidence[index] = replace(evidence[index], producer_identity="other-reviewer")
    with pytest.raises(NightShiftContractError, match="must match reviewer identity"):
        VerificationBundle(SHA, TASK, BUILDER, REVIEWER, tuple(evidence))


def test_builder_cannot_produce_independent_review() -> None:
    evidence = list(_evidence())
    index = next(
        i for i, item in enumerate(evidence)
        if item.gate is VerificationGate.INDEPENDENT_REVIEW
    )
    evidence[index] = replace(evidence[index], producer_identity=BUILDER)
    with pytest.raises(NightShiftContractError):
        VerificationBundle(SHA, TASK, BUILDER, BUILDER, tuple(evidence))


def test_failed_gate_produces_non_passing_quorum() -> None:
    bundle = VerificationBundle(
        SHA,
        TASK,
        BUILDER,
        REVIEWER,
        _evidence(failed_gate=VerificationGate.STATIC_SECURITY),
    )
    quorum = quorum_from_bundle(
        bundle,
        now_epoch=NOW,
        max_evidence_age_seconds=MAX_AGE,
    )
    assert not bundle.passed()
    assert not quorum.passed()


def test_evidence_requires_refs() -> None:
    with pytest.raises(NightShiftContractError, match="evidence refs"):
        VerificationEvidence(
            gate=VerificationGate.FOCUSED_TESTS,
            passed=True,
            subject_sha=SHA,
            task_capsule_digest=TASK,
            producer_identity=BUILDER,
            observed_at_epoch=10,
            evidence_digest="c" * 64,
            evidence_refs=(),
        )


def test_profile_declares_positive_evidence_ttl() -> None:
    assert load_verification_max_age_seconds(PROFILE) == MAX_AGE


def test_future_evidence_is_rejected() -> None:
    evidence = list(_evidence())
    evidence[0] = replace(evidence[0], observed_at_epoch=NOW + 1)
    bundle = VerificationBundle(SHA, TASK, BUILDER, REVIEWER, tuple(evidence))
    with pytest.raises(NightShiftContractError, match="observed in the future"):
        quorum_from_bundle(
            bundle,
            now_epoch=NOW,
            max_evidence_age_seconds=MAX_AGE,
        )


def test_expired_evidence_is_rejected() -> None:
    bundle = _bundle()
    with pytest.raises(NightShiftContractError, match="evidence expired"):
        quorum_from_bundle(
            bundle,
            now_epoch=10 + MAX_AGE,
            max_evidence_age_seconds=MAX_AGE,
        )
