from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from core.cirp.contracts import CIRPContractError
from core.cirp.engine import CIRPRunRequest
from core.cirp.governance import (
    RulePackApproval,
    RulePackFreshnessPolicy,
    RulePackRegistry,
)
from core.cirp.governed_runtime import (
    GovernedCanonicalCIRPRuntime,
    canonical_governance_request_digest,
)
from tests.test_cirp_canonical_runtime import NOW, request


def governance_for(
    selected_request: CIRPRunRequest | None = None,
    *,
    approval_age_days: int = 0,
    revoked: bool = False,
    max_approval_age_days: int = 30,
    max_source_age_days: int = 30,
) -> tuple[RulePackRegistry, RulePackFreshnessPolicy]:
    selected = selected_request or request()
    pack = selected.rule_packs[0]
    approval_time = selected.run_identity.evaluation_time - timedelta(days=approval_age_days)
    approval = RulePackApproval(
        approval_id="approval:p03:synthetic:1",
        pack_id=pack.pack_id,
        pack_digest=pack.digest(),
        verified_at=approval_time,
        approved_by="governance:p03:synthetic",
        revoked_at=(approval_time + timedelta(hours=1)) if revoked else None,
    )
    registry = RulePackRegistry(
        registry_id="registry:cirp:p03:synthetic",
        version="1",
        approvals=(approval,),
    )
    policy = RulePackFreshnessPolicy(
        policy_id="freshness:cirp:p03:synthetic",
        version="1",
        max_approval_age_days=max_approval_age_days,
        max_source_age_days=max_source_age_days,
        require_verified_sources=True,
    )
    return registry, policy


def test_governed_runtime_binds_approval_policy_run_request_and_replay() -> None:
    selected = request()
    registry, policy = governance_for(selected)
    runtime = GovernedCanonicalCIRPRuntime(
        registry=registry,
        freshness_policy=policy,
    )

    first = runtime.run(selected)
    second = runtime.run(selected)

    assert first.governance_receipt is not None
    assert first.replay_manifest is not None
    assert first.governance_receipt.run_identity_digest == selected.run_identity.digest()
    assert first.governance_receipt.request_digest == canonical_governance_request_digest(selected)
    assert first.governance_receipt.rule_pack_set_digest == selected.run_identity.rule_pack_digest
    assert first.replay_manifest.run_identity_digest == selected.run_identity.digest()
    assert first.replay_manifest.request_digest == canonical_governance_request_digest(selected)
    assert first.replay_manifest.digest() == second.replay_manifest.digest()
    assert (
        first.replay_manifest.canonical_replay_digest
        == first.canonical_result.replay_manifest.digest()
    )


def test_intrinsically_valid_rule_pack_without_exact_approval_fails_closed() -> None:
    selected = request()
    pack = selected.rule_packs[0]
    registry = RulePackRegistry(
        registry_id="registry:cirp:p03:synthetic",
        version="1",
        approvals=(
            RulePackApproval(
                approval_id="approval:p03:wrong-digest",
                pack_id=pack.pack_id,
                pack_digest="0" * 64,
                verified_at=selected.run_identity.evaluation_time,
                approved_by="governance:p03:synthetic",
            ),
        ),
    )
    _, policy = governance_for(selected)

    with pytest.raises(CIRPContractError, match="exact digest"):
        GovernedCanonicalCIRPRuntime(
            registry=registry,
            freshness_policy=policy,
        ).run(selected)


def test_stale_approval_fails_closed_under_versioned_policy() -> None:
    selected = request()
    registry, policy = governance_for(
        selected,
        approval_age_days=31,
        max_approval_age_days=30,
    )

    with pytest.raises(CIRPContractError, match="approval is stale"):
        GovernedCanonicalCIRPRuntime(
            registry=registry,
            freshness_policy=policy,
        ).run(selected)


def test_revoked_approval_fails_closed() -> None:
    selected = request()
    registry, policy = governance_for(selected, approval_age_days=1, revoked=True)

    with pytest.raises(CIRPContractError, match="approval is revoked"):
        GovernedCanonicalCIRPRuntime(
            registry=registry,
            freshness_policy=policy,
        ).run(selected)


def test_stale_legal_source_fails_closed_without_mutating_pack_validity() -> None:
    selected = request()
    future_identity = replace(
        selected.run_identity,
        evaluation_time=selected.run_identity.evaluation_time + timedelta(days=2),
    )
    evaluated_later = replace(selected, run_identity=future_identity)
    registry, policy = governance_for(
        evaluated_later,
        max_approval_age_days=30,
        max_source_age_days=1,
    )

    assert evaluated_later.rule_packs[0].digest() == selected.rule_packs[0].digest()
    with pytest.raises(CIRPContractError, match="source freshness limit"):
        GovernedCanonicalCIRPRuntime(
            registry=registry,
            freshness_policy=policy,
        ).run(evaluated_later)


def test_evaluation_time_is_explicit_and_changes_governance_proof() -> None:
    selected = request()
    later = replace(
        selected,
        run_identity=replace(
            selected.run_identity,
            evaluation_time=selected.run_identity.evaluation_time + timedelta(hours=1),
        ),
    )
    registry, policy = governance_for(selected)
    runtime = GovernedCanonicalCIRPRuntime(registry=registry, freshness_policy=policy)

    first = runtime.run(selected)
    second = runtime.run(later)

    assert first.governance_receipt is not None
    assert second.governance_receipt is not None
    assert first.replay_manifest is not None
    assert second.replay_manifest is not None
    assert first.governance_receipt.digest() != second.governance_receipt.digest()
    assert first.replay_manifest.digest() != second.replay_manifest.digest()


def test_rule_packs_without_governance_context_fail_closed() -> None:
    with pytest.raises(CIRPContractError, match="require registry approval"):
        GovernedCanonicalCIRPRuntime(
            registry=None,
            freshness_policy=None,
        ).run(request())
