from __future__ import annotations

from copy import deepcopy

import pytest

from core import replay_revalidation_invalidation_v1 as invalidation
from core.p3.contracts import RuntimeIdentity

D = {
    key: character * 64
    for key, character in {
        "config": "1",
        "corpus": "2",
        "input": "3",
        "evidence": "4",
        "lock": "5",
        "bundle": "6",
        "ssc": "7",
        "env_a": "8",
        "env_b": "9",
        "replay": "a",
        "migration": "b",
        "canon": "c",
        "crypto": "d",
        "storage": "e",
    }.items()
}


def _runtime(*, code_sha: str = "a" * 40, provider: str = "provider.alpha@1") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code_sha,
        schema_version="case-v2",
        config_digest=D["config"],
        corpus_digest=D["corpus"],
        provider_identities=(provider,),
        plugin_identities=("plugin.alpha@1",),
        input_digests=(D["input"],),
        evidence_digests=(D["evidence"],),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest=D["lock"],
        python_implementation="CPython",
        python_version="3.14.7",
        platform_tag="win_amd64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _fingerprint(runtime: RuntimeIdentity) -> invalidation.ReplayRevalidationFingerprintV1:
    return invalidation.ReplayRevalidationFingerprintV1.build(
        runtime_identity=runtime,
        lrd01i_bundle_digest=D["bundle"],
        ssc02_manifest_digest=D["ssc"],
        environment_profile_digests=(D["env_a"], D["env_b"]),
        replay_policy_digest=D["replay"],
        migration_registry_digest=D["migration"],
        canonicalization_profile_digest=D["canon"],
        crypto_profile_digest=D["crypto"],
        storage_profile_digests=(D["storage"],),
    )


def test_non_enum_domain_fails_with_contract_error_not_attribute_error() -> None:
    fingerprint = _fingerprint(_runtime())
    with pytest.raises(invalidation.ReplayRevalidationError, match="unknown domain"):
        invalidation.ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=fingerprint.fingerprint_digest,
            candidate_fingerprint_digest=fingerprint.fingerprint_digest,
            state=invalidation.ReplayRevalidationState.REVALIDATION_REQUIRED,
            changed_domains=("CODE",),  # type: ignore[arg-type]
            changed_fields=("runtime.code_sha",),
            violations=(),
        )


def test_non_string_decision_text_fails_with_contract_error() -> None:
    fingerprint = _fingerprint(_runtime())
    with pytest.raises(invalidation.ReplayRevalidationError, match="canonical nonblank text"):
        invalidation.ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=fingerprint.fingerprint_digest,
            candidate_fingerprint_digest=fingerprint.fingerprint_digest,
            state=invalidation.ReplayRevalidationState.REVALIDATION_REQUIRED,
            changed_domains=(invalidation.ReplayChangeDomain.CODE,),
            changed_fields=(7,),  # type: ignore[arg-type]
            violations=(),
        )


def test_fingerprint_rejects_noncanonical_order_and_duplicate_serialization() -> None:
    fingerprint = _fingerprint(_runtime())
    reversed_inventory = deepcopy(fingerprint.canonical_dict())
    reversed_inventory["environment_profile_digests"] = [D["env_b"], D["env_a"]]
    with pytest.raises(invalidation.ReplayRevalidationError, match="not canonical"):
        invalidation.ReplayRevalidationFingerprintV1.from_dict(reversed_inventory)

    duplicate = deepcopy(fingerprint.canonical_dict())
    duplicate["storage_profile_digests"] = [D["storage"], D["storage"]]
    with pytest.raises(invalidation.ReplayRevalidationError, match="not canonical"):
        invalidation.ReplayRevalidationFingerprintV1.from_dict(duplicate)


def test_uppercase_or_whitespace_digest_is_not_canonical_identity() -> None:
    fingerprint = _fingerprint(_runtime())
    uppercase = deepcopy(fingerprint.canonical_dict())
    uppercase["replay_policy_digest"] = D["replay"].upper()
    with pytest.raises(invalidation.ReplayRevalidationError, match="canonical lowercase"):
        invalidation.ReplayRevalidationFingerprintV1.from_dict(uppercase)

    whitespace = deepcopy(fingerprint.canonical_dict())
    whitespace["ssc02_manifest_digest"] = D["ssc"] + " "
    with pytest.raises(invalidation.ReplayRevalidationError, match="canonical nonblank text"):
        invalidation.ReplayRevalidationFingerprintV1.from_dict(whitespace)


def test_decision_parser_rejects_non_string_domain_and_text() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(code_sha="b" * 40)
    decision = invalidation.evaluate_revalidation_requirement_v1(
        baseline=_fingerprint(baseline_runtime),
        candidate=_fingerprint(candidate_runtime),
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
    )

    invalid_domain = deepcopy(decision.canonical_dict())
    invalid_domain["changed_domains"] = [7]
    with pytest.raises(invalidation.ReplayRevalidationError, match="canonical nonblank text"):
        invalidation.ReplayRevalidationDecisionV1.from_dict(invalid_domain)

    invalid_field = deepcopy(decision.canonical_dict())
    invalid_field["changed_fields"] = [7]
    with pytest.raises(invalidation.ReplayRevalidationError, match="canonical nonblank text"):
        invalidation.ReplayRevalidationDecisionV1.from_dict(invalid_field)


def test_decision_rejects_noncanonical_change_inventory_order() -> None:
    baseline_runtime = _runtime()
    candidate_runtime = _runtime(code_sha="b" * 40, provider="provider.beta@2")
    decision = invalidation.evaluate_revalidation_requirement_v1(
        baseline=_fingerprint(baseline_runtime),
        candidate=_fingerprint(candidate_runtime),
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
    )
    assert len(decision.changed_domains) == 2
    noncanonical = deepcopy(decision.canonical_dict())
    raw_domains = noncanonical["changed_domains"]
    raw_fields = noncanonical["changed_fields"]
    assert isinstance(raw_domains, list)
    assert isinstance(raw_fields, list)
    noncanonical["changed_domains"] = list(reversed(raw_domains))
    noncanonical["changed_fields"] = list(reversed(raw_fields))
    with pytest.raises(invalidation.ReplayRevalidationError, match="not canonical"):
        invalidation.ReplayRevalidationDecisionV1.from_dict(noncanonical)
