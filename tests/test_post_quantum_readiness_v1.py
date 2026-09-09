from __future__ import annotations

import copy
import inspect

import pytest

import core.post_quantum_readiness_v1 as pqc_module
from core.crypto_agility_v1 import (
    CryptoKeyStatus,
    CryptoTrustKeyV1,
    CryptoTrustSetV1,
)
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.long_range_health_v1 import (
    HealthDimensionState,
    LongRangeHealthReportV1,
    LongRangeHealthState,
)
from core.post_quantum_readiness_v1 import (
    ArchivalRenewalPlanStateV1,
    ArchivalRenewalPlanV1,
    PostQuantumReadinessError,
    PqcMigrationPolicyV1,
    PqcReadinessReportV1,
    PqcReadinessStateV1,
    PqcTargetFamilyProfileV1,
    PqcTargetFamilyV1,
    build_archival_renewal_plan_v1,
    build_pqc_readiness_report_v1,
    default_pqc_targets_v1,
)

_CASE = "CASE-PQC-01"


def _key(signer: AttestationSigner, *, not_before: int = 100) -> CryptoTrustKeyV1:
    return CryptoTrustKeyV1.from_public_key_bytes(
        key_id=signer.key_id,
        public_key=signer.public_key_bytes(),
        status=CryptoKeyStatus.ACTIVE,
        not_before=not_before,
        allowed_purposes=(AttestationPurpose.PROVENANCE,),
    )


def _trust_set(*, two_keys: bool = False) -> CryptoTrustSetV1:
    first = AttestationSigner.generate("classical-b")
    if not two_keys:
        return CryptoTrustSetV1(keys=(_key(first),))
    second = AttestationSigner.generate("classical-a")
    return CryptoTrustSetV1(keys=(_key(first), _key(second, not_before=110)))


def _health(
    *,
    case_id: str = _CASE,
    state: LongRangeHealthState = LongRangeHealthState.HEALTHY,
    evaluated_at: int = 500,
) -> LongRangeHealthReportV1:
    if state is LongRangeHealthState.HEALTHY:
        crypto_state = HealthDimensionState.FRESH
        portability_state = HealthDimensionState.FRESH
        recovery_state = HealthDimensionState.FRESH
        violations: tuple[str, ...] = ()
        crypto_digest: str | None = "a" * 64
        portability_digest: str | None = "b" * 64
        recovery_digest: str | None = "c" * 64
    elif state is LongRangeHealthState.STALE:
        crypto_state = HealthDimensionState.STALE
        portability_state = HealthDimensionState.FRESH
        recovery_state = HealthDimensionState.FRESH
        violations = ("crypto_renewal_stale",)
        crypto_digest = "a" * 64
        portability_digest = "b" * 64
        recovery_digest = "c" * 64
    else:
        crypto_state = HealthDimensionState.MISSING
        portability_state = HealthDimensionState.FRESH
        recovery_state = HealthDimensionState.FRESH
        violations = ("crypto_renewal_missing",)
        crypto_digest = None
        portability_digest = "b" * 64
        recovery_digest = "c" * 64
    return LongRangeHealthReportV1(
        case_id=case_id,
        evaluated_at=evaluated_at,
        freshness_policy_digest="d" * 64,
        drift_report_digest="e" * 64,
        crypto_state=crypto_state,
        portability_state=portability_state,
        recovery_state=recovery_state,
        crypto_evidence_digest=crypto_digest,
        portability_evidence_digest=portability_digest,
        recovery_evidence_digest=recovery_digest,
        state=state,
        violations=violations,
    )


def _readiness(
    *,
    health: LongRangeHealthReportV1 | None = None,
    trust_set: CryptoTrustSetV1 | None = None,
) -> tuple[PqcMigrationPolicyV1, PqcReadinessReportV1, LongRangeHealthReportV1]:
    actual_health = health or _health()
    actual_trust = trust_set or _trust_set()
    policy = PqcMigrationPolicyV1.default()
    report = build_pqc_readiness_report_v1(
        case_id=actual_health.case_id,
        health_report=actual_health,
        current_trust_set=actual_trust,
        policy=policy,
        evaluated_at=actual_health.evaluated_at + 10,
    )
    return policy, report, actual_health


def test_fixed_target_registry_binds_both_nist_signature_families() -> None:
    targets = default_pqc_targets_v1()

    assert [item.family for item in targets] == [
        PqcTargetFamilyV1.ML_DSA,
        PqcTargetFamilyV1.SLH_DSA,
    ]
    assert [item.standard_id for item in targets] == [
        "NIST-FIPS-204",
        "NIST-FIPS-205",
    ]
    assert all(item.adapter_required for item in targets)
    assert all(item.operational_parameter_set is None for item in targets)


def test_policy_registry_cannot_be_reduced_or_claim_adapter_support() -> None:
    with pytest.raises(PostQuantumReadinessError, match="cannot be reduced"):
        PqcMigrationPolicyV1(targets=(default_pqc_targets_v1()[0],))

    with pytest.raises(PostQuantumReadinessError, match="cannot claim"):
        PqcTargetFamilyProfileV1(
            family=PqcTargetFamilyV1.ML_DSA,
            standard_id="NIST-FIPS-204",
            role=default_pqc_targets_v1()[0].role,
            adapter_required=False,
        )


def test_policy_round_trip_is_strict_and_content_addressed() -> None:
    policy = PqcMigrationPolicyV1.default()

    restored = PqcMigrationPolicyV1.from_dict(policy.serialized())

    assert restored == policy
    assert restored.policy_digest == policy.policy_digest


def test_healthy_case_is_adapter_required_never_pqc_supported() -> None:
    policy, report, _ = _readiness()

    assert report.state is PqcReadinessStateV1.ADAPTER_REQUIRED
    assert report.post_quantum_support is False
    assert report.blockers == ("pqc_adapter_not_implemented",)
    assert report.migration_policy_digest == policy.policy_digest
    assert {surface.algorithm.value for surface in report.signature_surfaces} == {
        "ED25519"
    }


def test_signature_inventory_order_is_deterministic() -> None:
    trust_set = _trust_set(two_keys=True)
    _, report, _ = _readiness(trust_set=trust_set)

    assert [surface.key_id for surface in report.signature_surfaces] == sorted(
        surface.key_id for surface in report.signature_surfaces
    )
    restored = PqcReadinessReportV1.from_dict(report.canonical_dict())
    assert restored.report_digest == report.report_digest


def test_nonhealthy_current_evidence_blocks_migration_readiness() -> None:
    _, report, _ = _readiness(health=_health(state=LongRangeHealthState.STALE))

    assert report.state is PqcReadinessStateV1.BLOCKED_CURRENT_HEALTH
    assert report.blockers == (
        "current_long_range_health_not_healthy",
        "pqc_adapter_not_implemented",
    )


def test_cross_case_and_future_assessment_inputs_fail_closed() -> None:
    health = _health(case_id="CASE-A")
    policy = PqcMigrationPolicyV1.default()
    trust_set = _trust_set()

    with pytest.raises(PostQuantumReadinessError, match="case scope"):
        build_pqc_readiness_report_v1(
            case_id="CASE-B",
            health_report=health,
            current_trust_set=trust_set,
            policy=policy,
            evaluated_at=600,
        )

    with pytest.raises(PostQuantumReadinessError, match="cannot predate"):
        build_pqc_readiness_report_v1(
            case_id="CASE-A",
            health_report=health,
            current_trust_set=trust_set,
            policy=policy,
            evaluated_at=499,
        )


def test_unknown_fields_and_fake_pqc_support_fail_closed() -> None:
    _, report, _ = _readiness()
    raw = copy.deepcopy(report.canonical_dict())
    raw["future_field"] = "nope"
    with pytest.raises(PostQuantumReadinessError, match="unknown=future_field"):
        PqcReadinessReportV1.from_dict(raw)

    raw = copy.deepcopy(report.canonical_dict())
    raw["post_quantum_support"] = True
    with pytest.raises(PostQuantumReadinessError, match="cannot claim"):
        PqcReadinessReportV1.from_dict(raw)


def test_report_digest_tamper_fails_closed() -> None:
    _, report, _ = _readiness()
    raw = copy.deepcopy(report.canonical_dict())
    raw["report_digest"] = "f" * 64

    with pytest.raises(PostQuantumReadinessError, match="digest mismatch"):
        PqcReadinessReportV1.from_dict(raw)


def test_archival_plan_is_additive_and_preserves_classical_evidence() -> None:
    policy, report, health = _readiness()

    plan = build_archival_renewal_plan_v1(
        health_report=health,
        readiness_report=report,
        policy=policy,
    )

    assert plan.state is ArchivalRenewalPlanStateV1.READY_FOR_ADAPTER_IMPLEMENTATION
    assert plan.classical_crypto_evidence_digest == health.crypto_evidence_digest
    assert plan.preserve_original_evidence is True
    assert plan.additive_renewal_only is True
    assert plan.dual_verification_before_cutover is True
    assert plan.post_quantum_execution_authorized is False
    assert len(plan.target_profile_digests) == 2
    assert ArchivalRenewalPlanV1.from_dict(plan.canonical_dict()) == plan


def test_archival_plan_blocks_when_current_health_is_not_healthy() -> None:
    policy, report, health = _readiness(
        health=_health(state=LongRangeHealthState.UNVERIFIABLE)
    )

    plan = build_archival_renewal_plan_v1(
        health_report=health,
        readiness_report=report,
        policy=policy,
    )

    assert plan.state is ArchivalRenewalPlanStateV1.BLOCKED_CURRENT_HEALTH
    assert plan.classical_crypto_evidence_digest is None


def test_archival_plan_rejects_health_and_policy_substitution() -> None:
    policy, report, health = _readiness()
    substituted_health = _health(evaluated_at=501)

    with pytest.raises(PostQuantumReadinessError, match="different long-range health"):
        build_archival_renewal_plan_v1(
            health_report=substituted_health,
            readiness_report=report,
            policy=policy,
        )

    raw = policy.serialized()
    raw["policy_digest"] = "f" * 64
    with pytest.raises(PostQuantumReadinessError, match="digest mismatch"):
        PqcMigrationPolicyV1.from_dict(raw)

    assert health.report_digest == report.health_report_digest


def test_archival_plan_tamper_and_execution_authority_fail_closed() -> None:
    policy, report, health = _readiness()
    plan = build_archival_renewal_plan_v1(
        health_report=health,
        readiness_report=report,
        policy=policy,
    )
    raw = copy.deepcopy(plan.canonical_dict())
    raw["post_quantum_execution_authorized"] = True

    with pytest.raises(PostQuantumReadinessError, match="cannot authorize"):
        ArchivalRenewalPlanV1.from_dict(raw)


def test_module_has_no_signing_or_canonical_ledger_write_path() -> None:
    source = inspect.getsource(pqc_module)

    assert "sign_attestation_v1" not in source
    assert "CanonicalCaseLedger" not in source
    assert "restore_case(" not in source
    assert "append_event(" not in source
