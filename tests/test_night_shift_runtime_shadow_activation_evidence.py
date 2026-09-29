from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_shadow_activation_evidence import (
    RuntimeShadowActivationRun,
    RuntimeShadowEvidencePolicy,
    RuntimeShadowEvidenceStatus,
    evaluate_runtime_shadow_evidence,
)
from core.night_shift.runtime_shadow_activation_plan import (
    RuntimeShadowActivationCandidate,
    RuntimeShadowActivationPlanResult,
    RuntimeShadowActivationPlanStatus,
)
from core.p3.contracts import content_digest


def _plan() -> RuntimeShadowActivationPlanResult:
    candidates = tuple(
        RuntimeShadowActivationCandidate(
            runtime_id=runtime_id,
            binding_candidate_digest=content_digest({"binding": runtime_id}),
            task_budget=1,
            shadow_only=True,
            rollback_required=True,
        )
        for runtime_id in ("dbos", "temporal")
    )
    return RuntimeShadowActivationPlanResult(
        status=RuntimeShadowActivationPlanStatus.READY_FOR_CONTROLLED_SHADOW_EXECUTION,
        policy_digest=content_digest({"policy": "v2-21"}),
        verification_digest=content_digest({"verification": "v2-20"}),
        proposal_digest=content_digest({"proposal": "v2-19"}),
        candidates=candidates,
        blockers=(),
    )


def _runs(
    plan: RuntimeShadowActivationPlanResult,
) -> tuple[RuntimeShadowActivationRun, ...]:
    out = []
    for candidate in plan.candidates:
        for index in range(3):
            out.append(
                RuntimeShadowActivationRun(
                    runtime_id=candidate.runtime_id,
                    plan_candidate_digest=candidate.digest(),
                    run_id=f"{candidate.runtime_id}-shadow-{index}",
                    side_effect_free=True,
                    rollback_verified=True,
                    deterministic_replay_pass=True,
                    task_budget_respected=True,
                    evidence_digest=content_digest(
                        {"runtime": candidate.runtime_id, "run": index}
                    ),
                    evidence_refs=(
                        f"artifact:{candidate.runtime_id}:shadow:{index}",
                    ),
                )
            )
    return tuple(out)


def test_v222_requires_three_clean_shadow_runs_per_runtime() -> None:
    plan = _plan()
    result = evaluate_runtime_shadow_evidence(
        plan=plan,
        runs=_runs(plan),
        policy=RuntimeShadowEvidencePolicy(),
    )

    assert result.status is RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW
    assert all(item.ready_for_promotion_review for item in result.candidates)
    assert not result.production_promotion_executed


def test_v222_failed_rollback_blocks_promotion_review() -> None:
    plan = _plan()
    runs = _runs(plan)
    poisoned = replace(runs[0], rollback_verified=False)
    result = evaluate_runtime_shadow_evidence(
        plan=plan,
        runs=(poisoned,) + runs[1:],
        policy=RuntimeShadowEvidencePolicy(),
    )

    assert result.status is RuntimeShadowEvidenceStatus.BLOCKED
    assert "SHADOW_EXECUTION_REQUIREMENTS_FAILED" in result.candidates[0].blockers


def test_v222_duplicate_evidence_cannot_inflate_run_count() -> None:
    plan = _plan()
    runs = _runs(plan)
    duplicated = replace(runs[1], evidence_digest=runs[0].evidence_digest)

    with pytest.raises(
        NightShiftContractError,
        match="evidence digests must be globally unique",
    ):
        evaluate_runtime_shadow_evidence(
            plan=plan,
            runs=(runs[0], duplicated) + runs[2:],
            policy=RuntimeShadowEvidencePolicy(),
        )


def test_v222_policy_cannot_lower_three_run_floor() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="at least three shadow runs",
    ):
        RuntimeShadowEvidencePolicy(min_runs_per_runtime=2)

def test_v222_ready_evidence_cannot_carry_blockers() -> None:
    plan = _plan()
    result = evaluate_runtime_shadow_evidence(
        plan=plan,
        runs=_runs(plan),
        policy=RuntimeShadowEvidencePolicy(),
    )

    with pytest.raises(
        NightShiftContractError,
        match="ready shadow evidence cannot carry blockers",
    ):
        replace(result, blockers=("FORGED_BLOCKER",))
