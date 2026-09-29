from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_binding_proposal import (
    RuntimeBindingProposalCandidate,
    RuntimeBindingProposalResult,
    RuntimeBindingProposalStatus,
)
from core.night_shift.runtime_binding_verification import (
    RuntimeBindingVerificationResult,
    RuntimeBindingVerificationStatus,
)
from core.night_shift.runtime_shadow_activation_plan import (
    RuntimeShadowActivationPlanStatus,
    RuntimeShadowActivationPolicy,
    build_runtime_shadow_activation_plan,
)
from core.p3.contracts import content_digest


def _proposal() -> RuntimeBindingProposalResult:
    candidates = tuple(
        RuntimeBindingProposalCandidate(
            runtime_id=runtime_id,
            binding_id=f"{runtime_id}:{runtime_id}_adapter",
            adapter_name=f"{runtime_id}_adapter",
            profile_digest=content_digest({"profile": runtime_id}),
            artifact_digest=content_digest({"artifact": runtime_id}),
            admission_candidate_digest=content_digest({"admission": runtime_id}),
        )
        for runtime_id in ("dbos", "temporal")
    )
    return RuntimeBindingProposalResult(
        status=RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE,
        policy_digest=content_digest({"policy": "v2-19"}),
        admission_digest=content_digest({"admission": "v2-18"}),
        subject_repo_sha="a" * 40,
        candidates=candidates,
        blockers=(),
    )


def _verification(proposal: RuntimeBindingProposalResult) -> RuntimeBindingVerificationResult:
    return RuntimeBindingVerificationResult(
        status=RuntimeBindingVerificationStatus.READY_FOR_SHADOW_ACTIVATION_PLAN,
        policy_digest=content_digest({"policy": "v2-20"}),
        proposal_digest=proposal.digest(),
        signed_proposal_digest=content_digest({"signed": "proposal"}),
        trust_set_digest=content_digest({"trust": "set"}),
        signer_identity="runtime-binding-reviewer",
        signature_verification_digest=content_digest({"verification": "signature"}),
        observation_digests=(
            content_digest({"observation": "dbos"}),
            content_digest({"observation": "temporal"}),
        ),
        registry_snapshot_digest=content_digest({"registry": "snapshot"}),
        matrix_snapshot_digest=content_digest({"matrix": "snapshot"}),
        blockers=(),
    )


def test_v221_builds_bounded_shadow_only_plan() -> None:
    proposal = _proposal()
    result = build_runtime_shadow_activation_plan(
        proposal=proposal,
        verification=_verification(proposal),
        policy=RuntimeShadowActivationPolicy(),
    )

    assert (
        result.status
        is RuntimeShadowActivationPlanStatus.READY_FOR_CONTROLLED_SHADOW_EXECUTION
    )
    assert all(item.task_budget == 1 for item in result.candidates)
    assert all(item.shadow_only and item.rollback_required for item in result.candidates)
    assert not result.execution_started


def test_v221_rejects_verification_proposal_drift() -> None:
    proposal = _proposal()
    verification = replace(
        _verification(proposal),
        proposal_digest=content_digest({"proposal": "other"}),
    )
    with pytest.raises(
        NightShiftContractError,
        match="does not bind exact proposal",
    ):
        build_runtime_shadow_activation_plan(
            proposal=proposal,
            verification=verification,
            policy=RuntimeShadowActivationPolicy(),
        )


def test_v221_policy_cannot_enable_production_mutation() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="cannot publish, mutate production, or auto-promote",
    ):
        RuntimeShadowActivationPolicy(production_mutation_enabled=True)

def test_v221_ready_plan_cannot_carry_blockers() -> None:
    proposal = _proposal()
    result = build_runtime_shadow_activation_plan(
        proposal=proposal,
        verification=_verification(proposal),
        policy=RuntimeShadowActivationPolicy(),
    )

    with pytest.raises(
        NightShiftContractError,
        match="ready shadow activation plan cannot carry blockers",
    ):
        replace(result, blockers=("FORGED_BLOCKER",))
