from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import lukart_build_backend
from core.p3.contracts import (
    RUNTIME_IDENTITY_V2,
    RUNTIME_IDENTITY_V3,
    P3ContractError,
    RuntimeIdentity,
    enrich_runtime_identity_v2,
)


def _base_identity(**overrides: object) -> RuntimeIdentity:
    values: dict[str, object] = {
        "code_sha": "a" * 40,
        "schema_version": "case.v1",
        "config_digest": "b" * 64,
        "corpus_digest": "c" * 64,
        "provider_identities": ("provider@1",),
        "plugin_identities": ("plugin@1",),
        "input_digests": ("d" * 64,),
        "evidence_digests": ("e" * 64,),
        "provider_inventory_declared": True,
        "plugin_inventory_declared": True,
        "input_inventory_declared": True,
        "evidence_inventory_declared": True,
        "dependency_lock_digest": "f" * 64,
        "python_implementation": "cpython",
        "python_version": "3.14.7",
        "platform_tag": "linux-x86_64",
        "project_version": "1.1.0.dev0",
        "build_backend": "lukart_build_backend:setuptools==80.9.0",
        "execution_environment_declared": True,
    }
    values.update(overrides)
    return RuntimeIdentity(**values)  # type: ignore[arg-type]


def test_ph02_runtime_identity_v3_is_complete_and_deterministic() -> None:
    first = _base_identity(provider_identities=("z@2", "a@1"))
    second = _base_identity(provider_identities=("a@1", "z@2"))
    assert first.identity_schema == RUNTIME_IDENTITY_V3
    assert first.complete_for_replay
    assert first.digest() == second.digest()


def test_ph02_v3_missing_execution_identity_fails_closed() -> None:
    with pytest.raises(P3ContractError, match="execution identity is incomplete"):
        _base_identity(python_version="")


def test_ph02_v2_remains_readable_but_never_complete_for_v3_replay() -> None:
    legacy = RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        identity_schema=RUNTIME_IDENTITY_V2,
    )
    assert not legacy.complete_for_replay
    assert "execution_environment" in legacy.incomplete_fields()


def test_ph02_v2_enrichment_requires_explicit_execution_evidence() -> None:
    legacy = RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        identity_schema=RUNTIME_IDENTITY_V2,
    )
    enriched = enrich_runtime_identity_v2(
        legacy,
        dependency_lock_digest="f" * 64,
        python_implementation="cpython",
        python_version="3.14.7",
        platform_tag="linux-x86_64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend:setuptools==80.9.0",
    )
    assert enriched.identity_schema == RUNTIME_IDENTITY_V3
    assert not enriched.complete_for_replay
    assert "provider_identities" in enriched.incomplete_fields()


def test_ph02_v3_cannot_be_enriched_as_v2() -> None:
    with pytest.raises(P3ContractError, match="requires a v2 source"):
        enrich_runtime_identity_v2(
            _base_identity(),
            dependency_lock_digest="f" * 64,
            python_implementation="cpython",
            python_version="3.14.7",
            platform_tag="linux-x86_64",
            project_version="1.1.0.dev0",
            build_backend="lukart_build_backend:setuptools==80.9.0",
        )


def test_ph02_current_source_is_not_historical_baseline() -> None:
    version, baseline, baseline_sha = lukart_build_backend._project_state()
    assert version == "1.1.0.dev0"
    assert baseline == "1.0.1"
    assert baseline_sha == "802013c4d0e53dc12306a97e1877ebba86af64a7"
    lukart_build_backend._enforce_immutable_baseline()


def test_ph02_lock_digest_is_sha256_when_lock_exists() -> None:
    lock = Path("uv.lock")
    if not lock.exists():
        pytest.skip("lock is generated in the PH-02 branch before final candidate validation")
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    assert len(digest) == 64
    int(digest, 16)
