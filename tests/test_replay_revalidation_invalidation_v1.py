from __future__ import annotations

from copy import deepcopy

import pytest

from core.p3.contracts import RuntimeIdentity
from core.replay_revalidation_invalidation_v1 import (
    ReplayChangeDomain,
    ReplayRevalidationDecisionV1,
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
    ReplayRevalidationState,
    evaluate_revalidation_requirement_v1,
    verify_revalidation_decision_v1,
)

D = {
    "config": "1" * 64,
    "corpus": "2" * 64,
    "input": "3" * 64,
    "evidence": "4" * 64,
    "lock": "5" * 64,
    "bundle": "6" * 64,
    "ssc": "7" * 64,
    "env_a": "8" * 64,
    "env_b": "9" * 64,
    "replay_policy": "a" * 64,
    "migration": "b" * 64,
    "canon": "c" * 64,
    "crypto": "d" * 64,
    "storage": "e" * 64,
}


def _runtime(**overrides: object) -> RuntimeIdentity:
    values: dict[str, object] = {
        "code_sha": "a" * 40,
        "schema_version": "case-v2",
        "config_digest": D["config"],
        "corpus_digest": D["corpus"],
        "provider_identities": ("provider.alpha@1",),
        "plugin_identities": ("plugin.alpha@1",),
        "input_digests": (D["input"],),
        "evidence_digests": (D["evidence"],),
        "provider_inventory_declared": True,
        "plugin_inventory_declared": True,
        "input_inventory_declared": True,
        "evidence_inventory_declared": True,
        "dependency_lock_digest": D["lock"],
        "python_implementation": "CPython",
        "python_version": "3.14.7",
        "platform_tag": "win_amd64",
        "project_version": "1.1.0.dev0",
        "build_backend": "lukart_build_backend",
        "execution_environment_declared": True,
    }
    values.update(overrides)
    return RuntimeIdentity(**values)  # type: ignore[arg-type]


def _fingerprint(
    runtime: RuntimeIdentity | None = None,
    **overrides: object,
) -> ReplayRevalidationFingerprintV1:
    values: dict[str, object] = {
        "lrd01i_bundle_digest": D["bundle"],
        "ssc02_manifest_digest": D["ssc"],
        "environment_profile_digests": (D["env_a"], D["env_b"]),
        "replay_policy_digest": D["replay_policy"],
        "migration_registry_digest": D["migration"],
        "canonicalization_profile_digest": D["canon"],
        "crypto_profile_digest": D["crypto"],
        "storage_profile_digests": (D["storage"],),
    }
    values.update(overrides)
    return ReplayRevalidationFingerprintV1.build(
        runtime_identity=runtime or _runtime(),
        **values,  # type: ignore[arg-type]
    )


def _decision(
    baseline: ReplayRevalidationFingerprintV1 | None,
    candidate: ReplayRevalidationFingerprintV1,
    baseline_runtime: RuntimeIdentity | None,
    candidate_runtime: RuntimeIdentity,
) -> ReplayRevalidationDecisionV1:
    return evaluate_revalidation_requirement_v1(
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
    )


def test_fingerprint_is_content_addressed_and_round_trips_strictly() -> None:
    fingerprint = _fingerprint()
    assert len(fingerprint.fingerprint_digest) == 64
    assert fingerprint.environment_profile_digests == (D["env_a"], D["env_b"])
    assert ReplayRevalidationFingerprintV1.from_dict(fingerprint.canonical_dict()) == fingerprint

    tampered = fingerprint.canonical_dict()
    tampered["storage_profile_digests"] = ["f" * 64]
    with pytest.raises(ReplayRevalidationError, match="fingerprint_digest mismatch"):
        ReplayRevalidationFingerprintV1.from_dict(tampered)


def test_exact_same_fingerprint_keeps_baseline_replay_reusable() -> None:
    runtime = _runtime()
    baseline = _fingerprint(runtime)
    candidate = _fingerprint(runtime)
    decision = _decision(baseline, candidate, runtime, runtime)
    assert decision.state is ReplayRevalidationState.UNCHANGED
    assert decision.changed_domains == ()
    assert decision.changed_fields == ()
    assert decision.baseline_replay_reusable is True
    assert verify_revalidation_decision_v1(
        decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=runtime,
        candidate_runtime_identity=runtime,
    ) == decision.decision_digest
    assert ReplayRevalidationDecisionV1.from_dict(decision.canonical_dict()) == decision


def test_code_change_invalidates_old_replay_without_claiming_new_pass() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(code_sha="b" * 40)
    decision = _decision(
        _fingerprint(baseline_runtime),
        _fingerprint(candidate_runtime),
        baseline_runtime,
        candidate_runtime,
    )
    assert decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
    assert decision.changed_domains == (ReplayChangeDomain.CODE,)
    assert decision.changed_fields == ("runtime.code_sha",)
    assert decision.baseline_replay_reusable is False
    assert decision.canonical_dict()["release_authority"] is False
    assert decision.canonical_dict()["scheduler_authority"] is False


def test_provider_change_is_explicit_revalidation_trigger() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(provider_identities=("provider.alpha@2",))
    decision = _decision(
        _fingerprint(baseline_runtime),
        _fingerprint(candidate_runtime),
        baseline_runtime,
        candidate_runtime,
    )
    assert decision.changed_domains == (ReplayChangeDomain.PROVIDER,)
    assert decision.changed_fields == ("runtime.provider_identities",)


def test_python_dependency_platform_and_build_changes_are_not_hidden() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(
        dependency_lock_digest="f" * 64,
        python_version="3.11.14",
        platform_tag="manylinux_2_39_x86_64",
        build_backend="setuptools.build_meta",
    )
    decision = _decision(
        _fingerprint(baseline_runtime),
        _fingerprint(candidate_runtime),
        baseline_runtime,
        candidate_runtime,
    )
    assert decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
    assert set(decision.changed_domains) == {
        ReplayChangeDomain.BUILD,
        ReplayChangeDomain.DEPENDENCY,
        ReplayChangeDomain.PLATFORM,
        ReplayChangeDomain.PYTHON,
    }
    assert "runtime.python_version" in decision.changed_fields
    assert "runtime.dependency_lock_digest" in decision.changed_fields


def test_replay_storage_and_migration_identity_changes_require_revalidation() -> None:
    runtime = _runtime()
    baseline = _fingerprint(runtime)
    candidate = _fingerprint(
        runtime,
        environment_profile_digests=(D["env_a"], "f" * 64),
        migration_registry_digest="0" * 64,
        crypto_profile_digest="f" * 64,
        storage_profile_digests=("0" * 64,),
    )
    decision = _decision(baseline, candidate, runtime, runtime)
    assert decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
    assert set(decision.changed_domains) == {
        ReplayChangeDomain.CRYPTO,
        ReplayChangeDomain.ENVIRONMENT,
        ReplayChangeDomain.MIGRATION,
        ReplayChangeDomain.STORAGE,
    }
    assert "storage_profile_digests" in decision.changed_fields
    assert "environment_profile_digests" in decision.changed_fields


def test_preserved_bundle_supply_chain_policy_and_canonicalization_are_triggers() -> None:
    runtime = _runtime()
    baseline = _fingerprint(runtime)
    candidate = _fingerprint(
        runtime,
        lrd01i_bundle_digest="f" * 64,
        ssc02_manifest_digest="0" * 64,
        replay_policy_digest="f" * 64,
        canonicalization_profile_digest="0" * 64,
    )
    decision = _decision(baseline, candidate, runtime, runtime)
    assert set(decision.changed_domains) == {
        ReplayChangeDomain.CANONICALIZATION,
        ReplayChangeDomain.PRESERVED_BUNDLE,
        ReplayChangeDomain.REPLAY_POLICY,
        ReplayChangeDomain.SUPPLY_CHAIN,
    }


def test_missing_baseline_is_unverifiable_and_never_reuses_old_pass() -> None:
    runtime = _runtime()
    candidate = _fingerprint(runtime)
    decision = _decision(None, candidate, None, runtime)
    assert decision.state is ReplayRevalidationState.UNVERIFIABLE
    assert decision.violations == ("baseline_revalidation_fingerprint_missing",)
    assert decision.baseline_replay_reusable is False
    assert decision.changed_domains == ()


def test_runtime_identity_substitution_fails_closed() -> None:
    runtime = _runtime()
    baseline = _fingerprint(runtime)
    candidate = _fingerprint(runtime)
    substituted = _runtime(code_sha="b" * 40)
    with pytest.raises(ReplayRevalidationError, match="candidate RuntimeIdentity substitution"):
        _decision(baseline, candidate, runtime, substituted)
    with pytest.raises(ReplayRevalidationError, match="baseline RuntimeIdentity substitution"):
        _decision(baseline, candidate, substituted, runtime)


def test_incomplete_runtime_cannot_create_authoritative_fingerprint() -> None:
    incomplete = _runtime(provider_inventory_declared=False)
    assert incomplete.complete_for_replay is False
    with pytest.raises(ReplayRevalidationError, match="complete for replay"):
        _fingerprint(incomplete)


def test_fingerprint_requires_complete_environment_and_storage_identity_sets() -> None:
    runtime = _runtime()
    with pytest.raises(ReplayRevalidationError, match="at least 2"):
        _fingerprint(runtime, environment_profile_digests=(D["env_a"],))
    with pytest.raises(ReplayRevalidationError, match="at least 1"):
        _fingerprint(runtime, storage_profile_digests=())


def test_unknown_fields_authority_injection_and_decision_tamper_fail_closed() -> None:
    runtime = _runtime()
    fingerprint = _fingerprint(runtime)
    unknown = fingerprint.canonical_dict()
    unknown["model_override"] = "provider.beta@9"
    with pytest.raises(ReplayRevalidationError, match="unknown=model_override"):
        ReplayRevalidationFingerprintV1.from_dict(unknown)

    decision = _decision(fingerprint, fingerprint, runtime, runtime)
    authority = decision.canonical_dict()
    authority["release_authority"] = True
    with pytest.raises(ReplayRevalidationError, match="release_authority"):
        ReplayRevalidationDecisionV1.from_dict(authority)

    tampered = deepcopy(decision.canonical_dict())
    tampered["state"] = "REVALIDATION_REQUIRED"
    with pytest.raises(ReplayRevalidationError):
        ReplayRevalidationDecisionV1.from_dict(tampered)


def test_multiple_runtime_domains_are_sorted_and_deterministic() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(
        code_sha="b" * 40,
        config_digest="f" * 64,
        provider_identities=("provider.beta@1",),
        project_version="1.2.0.dev0",
    )
    baseline = _fingerprint(baseline_runtime)
    candidate = _fingerprint(candidate_runtime)
    first = _decision(baseline, candidate, baseline_runtime, candidate_runtime)
    second = _decision(baseline, candidate, baseline_runtime, candidate_runtime)
    assert first == second
    assert first.decision_digest == second.decision_digest
    assert first.changed_fields == tuple(sorted(first.changed_fields))
    assert [item.value for item in first.changed_domains] == sorted(
        item.value for item in first.changed_domains
    )
