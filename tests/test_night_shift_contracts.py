from __future__ import annotations

import pytest

from core.night_shift.contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
    authorize_task,
)

HEX_A = "a" * 64
HEX_B = "b" * 64


def _policy() -> PolicyRef:
    return PolicyRef(policy_id="NS-POLICY", version="v2", policy_digest=HEX_A)


def _state() -> LiveStateSnapshot:
    return LiveStateSnapshot(
        snapshot_id="snapshot-001",
        repository="marcusdd720-ui/lukart-ros",
        branch="feat/night-shift-kernel-v2",
        base_sha=HEX_A,
        head_sha=HEX_B,
        observed_at_epoch=100,
        expires_at_epoch=200,
        evidence_refs=("git:head", "github:pr"),
    )


def _task(state: LiveStateSnapshot, policy: PolicyRef) -> TaskCapsule:
    return TaskCapsule(
        task_id="task-001",
        repository=state.repository,
        state_snapshot_digest=state.digest(),
        policy_digest=policy.policy_digest,
        objective="Implement one bounded contract slice.",
        risk_class=RiskClass.R2,
        allowed_paths=("core/night_shift/**", "tests/test_night_shift_contracts.py"),
        forbidden_paths=(".github/**",),
        acceptance_checks=("pytest focused", "ruff"),
    )


def _envelope() -> AutonomyEnvelope:
    return AutonomyEnvelope(
        envelope_id="night-001",
        issued_at_epoch=90,
        expires_at_epoch=300,
        repositories=("marcusdd720-ui/lukart-ros",),
        allowed_risk_classes=(RiskClass.R2,),
        max_tasks=2,
        promotion_mode=PromotionMode.HUMAN,
    )


def test_authorize_task_binds_policy_state_task_and_authority() -> None:
    policy = _policy()
    state = _state()
    task = _task(state, policy)
    envelope = _envelope()

    decision = authorize_task(
        policy=policy,
        state=state,
        task=task,
        envelope=envelope,
        now_epoch=150,
        decision_id="decision-001",
    )

    assert decision.state_snapshot_digest == state.digest()
    assert decision.task_capsule_digest == task.digest()
    assert decision.autonomy_envelope_digest == envelope.digest()
    assert len(decision.digest()) == 64
def test_stale_state_fails_closed() -> None:
    policy = _policy()
    state = _state()

    with pytest.raises(NightShiftContractError, match="state snapshot is stale"):
        authorize_task(
            policy=policy,
            state=state,
            task=_task(state, policy),
            envelope=_envelope(),
            now_epoch=200,
            decision_id="decision-stale",
        )


def test_task_bound_to_different_snapshot_fails_closed() -> None:
    policy = _policy()
    state = _state()
    task = TaskCapsule(
        task_id="task-stale",
        repository=state.repository,
        state_snapshot_digest="c" * 64,
        policy_digest=policy.policy_digest,
        objective="Attempt stale execution.",
        risk_class=RiskClass.R2,
        allowed_paths=("core/night_shift/**",),
        forbidden_paths=(),
        acceptance_checks=("pytest focused",),
    )

    with pytest.raises(NightShiftContractError, match="different state snapshot"):
        authorize_task(
            policy=policy,
            state=state,
            task=task,
            envelope=_envelope(),
            now_epoch=150,
            decision_id="decision-stale-binding",
        )


def test_repository_outside_authority_fails_closed() -> None:
    policy = _policy()
    state = _state()
    envelope = AutonomyEnvelope(
        envelope_id="wrong-repo",
        issued_at_epoch=90,
        expires_at_epoch=300,
        repositories=("marcusdd720-ui/other",),
        allowed_risk_classes=(RiskClass.R2,),
        max_tasks=1,
        promotion_mode=PromotionMode.HUMAN,
    )
    with pytest.raises(NightShiftContractError, match="outside authority envelope"):
        authorize_task(
            policy=policy,
            state=state,
            task=_task(state, policy),
            envelope=envelope,
            now_epoch=150,
            decision_id="decision-wrong-repo",
        )


def test_auto_promotion_cannot_include_high_risk_classes() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="automatic promotion authority cannot include R2/R3/R4",
    ):
        AutonomyEnvelope(
            envelope_id="unsafe-auto",
            issued_at_epoch=10,
            expires_at_epoch=20,
            repositories=("marcusdd720-ui/lukart-ros",),
            allowed_risk_classes=(RiskClass.R0, RiskClass.R3),
            max_tasks=1,
            promotion_mode=PromotionMode.AUTO,
        )


def test_task_paths_cannot_be_both_allowed_and_forbidden() -> None:
    policy = _policy()
    state = _state()

    with pytest.raises(NightShiftContractError, match="paths overlap"):
        TaskCapsule(
            task_id="bad-paths",
            repository=state.repository,
            state_snapshot_digest=state.digest(),
            policy_digest=policy.policy_digest,
            objective="Invalid task.",
            risk_class=RiskClass.R1,
            allowed_paths=("core/night_shift/**",),
            forbidden_paths=("core/night_shift/**",),
            acceptance_checks=("pytest",),
        )


def test_canonicalization_is_order_independent_for_set_like_fields() -> None:
    first = AutonomyEnvelope(
        envelope_id="canonical",
        issued_at_epoch=1,
        expires_at_epoch=9,
        repositories=("repo-b", "repo-a"),
        allowed_risk_classes=(RiskClass.R1, RiskClass.R0),
        max_tasks=3,
        promotion_mode=PromotionMode.PREAUTHORIZED,
    )
    second = AutonomyEnvelope(
        envelope_id="canonical",
        issued_at_epoch=1,
        expires_at_epoch=9,
        repositories=("repo-a", "repo-b"),
        allowed_risk_classes=(RiskClass.R0, RiskClass.R1),
        max_tasks=3,
        promotion_mode=PromotionMode.PREAUTHORIZED,
    )

    assert first.digest() == second.digest()
