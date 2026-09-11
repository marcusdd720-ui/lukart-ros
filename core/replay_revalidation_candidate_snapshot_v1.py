"""LRD-01T bounded replay-revalidation candidate snapshot v1.

This module materializes one caller-supplied candidate RuntimeIdentity and the
existing LRD-01M revalidation fingerprint into a deterministic, content-addressed
snapshot consumable by LRD-01S. It performs no repository discovery, watching,
scheduling, replay execution, provider/storage access, persistence, Product/CCL
write, release mutation, or mutable-pointer management.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from core.p3.contracts import P3ContractError, RuntimeIdentity, content_digest, require_hex_digest
from core.replay_revalidation_invalidation_v1 import (
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
)

REVALIDATION_RUNTIME_MATERIAL_SCHEMA_V1 = (
    "lukart.replay-revalidation-runtime-material.v1"
)
REVALIDATION_CANDIDATE_SNAPSHOT_SCHEMA_V1 = (
    "lukart.replay-revalidation-candidate-snapshot.v1"
)


class ReplayRevalidationCandidateSnapshotError(ValueError):
    """Fail-closed LRD-01T contract violation."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationCandidateSnapshotError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _git_sha(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ReplayRevalidationCandidateSnapshotError(
            f"{field} must be a lowercase 40-char git SHA"
        )
    try:
        normalized = require_hex_digest(value, field_name=field, lengths=(40,))
    except ValueError as exc:
        raise ReplayRevalidationCandidateSnapshotError(str(exc)) from exc
    if normalized != value:
        raise ReplayRevalidationCandidateSnapshotError(
            f"{field} must be a canonical lowercase 40-char git SHA"
        )
    return normalized


def _strict(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    field: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationCandidateSnapshotError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


def _string_list(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ReplayRevalidationCandidateSnapshotError(f"{field} must be a list")
    result: list[str] = []
    for item in value:
        result.append(_text(item, field=field))
    return tuple(result)


_RUNTIME_MATERIAL_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "config_digest",
        "corpus_digest",
        "provider_identities",
        "plugin_identities",
        "input_digests",
        "evidence_digests",
        "dependency_lock_digest",
        "python_implementation",
        "python_version",
        "platform_tag",
        "project_version",
        "build_backend",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationRuntimeMaterialV1:
    """Explicit source material for one complete RuntimeIdentity v3.

    ``code_sha`` is intentionally absent. The candidate repository SHA is the only
    source for that field, preventing a caller from composing two different code
    identities into one candidate snapshot. Inventories are explicit even when
    empty and are therefore marked declared when the RuntimeIdentity is built.
    """

    schema_version: str
    config_digest: str
    corpus_digest: str
    provider_identities: tuple[str, ...]
    plugin_identities: tuple[str, ...]
    input_digests: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    dependency_lock_digest: str
    python_implementation: str
    python_version: str
    platform_tag: str
    project_version: str
    build_backend: str
    schema: str = REVALIDATION_RUNTIME_MATERIAL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_RUNTIME_MATERIAL_SCHEMA_V1:
            raise ReplayRevalidationCandidateSnapshotError(
                f"unsupported runtime material schema: {self.schema}"
            )
        try:
            normalized = RuntimeIdentity(
                code_sha="0" * 40,
                schema_version=self.schema_version,
                config_digest=self.config_digest,
                corpus_digest=self.corpus_digest,
                provider_identities=self.provider_identities,
                plugin_identities=self.plugin_identities,
                input_digests=self.input_digests,
                evidence_digests=self.evidence_digests,
                provider_inventory_declared=True,
                plugin_inventory_declared=True,
                input_inventory_declared=True,
                evidence_inventory_declared=True,
                dependency_lock_digest=self.dependency_lock_digest,
                python_implementation=self.python_implementation,
                python_version=self.python_version,
                platform_tag=self.platform_tag,
                project_version=self.project_version,
                build_backend=self.build_backend,
                execution_environment_declared=True,
            )
        except P3ContractError as exc:
            raise ReplayRevalidationCandidateSnapshotError(
                f"invalid runtime material: {exc}"
            ) from exc
        object.__setattr__(self, "schema_version", normalized.schema_version)
        object.__setattr__(self, "config_digest", normalized.config_digest)
        object.__setattr__(self, "corpus_digest", normalized.corpus_digest)
        object.__setattr__(
            self, "provider_identities", normalized.provider_identities
        )
        object.__setattr__(self, "plugin_identities", normalized.plugin_identities)
        object.__setattr__(self, "input_digests", normalized.input_digests)
        object.__setattr__(self, "evidence_digests", normalized.evidence_digests)
        object.__setattr__(
            self, "dependency_lock_digest", normalized.dependency_lock_digest
        )
        object.__setattr__(
            self, "python_implementation", normalized.python_implementation
        )
        object.__setattr__(self, "python_version", normalized.python_version)
        object.__setattr__(self, "platform_tag", normalized.platform_tag)
        object.__setattr__(self, "project_version", normalized.project_version)
        object.__setattr__(self, "build_backend", normalized.build_backend)

    def build_runtime_identity(self, *, repository_sha: str) -> RuntimeIdentity:
        exact_sha = _git_sha(repository_sha, field="candidate_repository_sha")
        try:
            identity = RuntimeIdentity(
                code_sha=exact_sha,
                schema_version=self.schema_version,
                config_digest=self.config_digest,
                corpus_digest=self.corpus_digest,
                provider_identities=self.provider_identities,
                plugin_identities=self.plugin_identities,
                input_digests=self.input_digests,
                evidence_digests=self.evidence_digests,
                provider_inventory_declared=True,
                plugin_inventory_declared=True,
                input_inventory_declared=True,
                evidence_inventory_declared=True,
                dependency_lock_digest=self.dependency_lock_digest,
                python_implementation=self.python_implementation,
                python_version=self.python_version,
                platform_tag=self.platform_tag,
                project_version=self.project_version,
                build_backend=self.build_backend,
                execution_environment_declared=True,
            )
        except P3ContractError as exc:
            raise ReplayRevalidationCandidateSnapshotError(
                f"cannot materialize RuntimeIdentity: {exc}"
            ) from exc
        if not identity.complete_for_replay:
            raise ReplayRevalidationCandidateSnapshotError(
                "materialized RuntimeIdentity is incomplete for replay"
            )
        return identity

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "config_digest": self.config_digest,
            "corpus_digest": self.corpus_digest,
            "provider_identities": list(self.provider_identities),
            "plugin_identities": list(self.plugin_identities),
            "input_digests": list(self.input_digests),
            "evidence_digests": list(self.evidence_digests),
            "dependency_lock_digest": self.dependency_lock_digest,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "platform_tag": self.platform_tag,
            "project_version": self.project_version,
            "build_backend": self.build_backend,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationRuntimeMaterialV1:
        _strict(value, _RUNTIME_MATERIAL_KEYS, field="runtime material")
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            schema_version=_text(
                value.get("schema_version"), field="schema_version"
            ),
            config_digest=_text(value.get("config_digest"), field="config_digest"),
            corpus_digest=_text(value.get("corpus_digest"), field="corpus_digest"),
            provider_identities=_string_list(
                value.get("provider_identities"), field="provider_identities"
            ),
            plugin_identities=_string_list(
                value.get("plugin_identities"), field="plugin_identities"
            ),
            input_digests=_string_list(
                value.get("input_digests"), field="input_digests"
            ),
            evidence_digests=_string_list(
                value.get("evidence_digests"), field="evidence_digests"
            ),
            dependency_lock_digest=_text(
                value.get("dependency_lock_digest"), field="dependency_lock_digest"
            ),
            python_implementation=_text(
                value.get("python_implementation"), field="python_implementation"
            ),
            python_version=_text(value.get("python_version"), field="python_version"),
            platform_tag=_text(value.get("platform_tag"), field="platform_tag"),
            project_version=_text(
                value.get("project_version"), field="project_version"
            ),
            build_backend=_text(value.get("build_backend"), field="build_backend"),
        )
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationCandidateSnapshotError(
                "runtime material is not canonical"
            )
        return result


_AUTHORITY_FIELDS = (
    "repository_change_detection_authority",
    "scheduler_authority",
    "replay_execution_authority",
    "provider_authority",
    "storage_authority",
    "mutable_pointer_authority",
    "product_write_authority",
    "ccl_write_authority",
    "release_authority",
)

_SNAPSHOT_KEYS = frozenset(
    {
        "schema",
        "candidate_repository_sha",
        "runtime_material",
        "runtime_identity",
        "fingerprint",
        *_AUTHORITY_FIELDS,
        "snapshot_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationCandidateSnapshotV1:
    """Content-addressed one-shot candidate state for LRD-01S."""

    candidate_repository_sha: str
    runtime_material: ReplayRevalidationRuntimeMaterialV1
    fingerprint: ReplayRevalidationFingerprintV1
    schema: str = REVALIDATION_CANDIDATE_SNAPSHOT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_CANDIDATE_SNAPSHOT_SCHEMA_V1:
            raise ReplayRevalidationCandidateSnapshotError(
                f"unsupported candidate snapshot schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "candidate_repository_sha",
            _git_sha(
                self.candidate_repository_sha,
                field="candidate_repository_sha",
            ),
        )
        if not isinstance(self.runtime_material, ReplayRevalidationRuntimeMaterialV1):
            raise ReplayRevalidationCandidateSnapshotError(
                "runtime_material must be ReplayRevalidationRuntimeMaterialV1"
            )
        if not isinstance(self.fingerprint, ReplayRevalidationFingerprintV1):
            raise ReplayRevalidationCandidateSnapshotError(
                "fingerprint must be ReplayRevalidationFingerprintV1"
            )
        identity = self.runtime_identity
        if self.fingerprint.runtime_identity_digest != identity.digest():
            raise ReplayRevalidationCandidateSnapshotError(
                "fingerprint/RuntimeIdentity substitution detected"
            )

    @property
    def runtime_identity(self) -> RuntimeIdentity:
        return self.runtime_material.build_runtime_identity(
            repository_sha=self.candidate_repository_sha
        )

    @property
    def candidate(self) -> ReplayRevalidationFingerprintV1:
        return self.fingerprint

    @property
    def candidate_runtime_identity(self) -> RuntimeIdentity:
        return self.runtime_identity

    def handoff_inputs(
        self,
    ) -> tuple[ReplayRevalidationFingerprintV1, RuntimeIdentity, str]:
        """Return the exact three candidate inputs consumed by LRD-01S."""
        return self.fingerprint, self.runtime_identity, self.candidate_repository_sha

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "candidate_repository_sha": self.candidate_repository_sha,
            "runtime_material": self.runtime_material.canonical_dict(),
            "runtime_identity": self.runtime_identity.canonical_dict(),
            "fingerprint": self.fingerprint.canonical_dict(),
            **{field: False for field in _AUTHORITY_FIELDS},
        }

    @property
    def snapshot_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "snapshot_digest": self.snapshot_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationCandidateSnapshotV1:
        _strict(value, _SNAPSHOT_KEYS, field="candidate snapshot")
        for authority in _AUTHORITY_FIELDS:
            if value.get(authority) is not False:
                raise ReplayRevalidationCandidateSnapshotError(
                    f"{authority} must remain false"
                )
        raw_material = value.get("runtime_material")
        raw_identity = value.get("runtime_identity")
        raw_fingerprint = value.get("fingerprint")
        if not isinstance(raw_material, Mapping):
            raise ReplayRevalidationCandidateSnapshotError(
                "runtime_material must be an object"
            )
        if not isinstance(raw_identity, Mapping):
            raise ReplayRevalidationCandidateSnapshotError(
                "runtime_identity must be an object"
            )
        if not isinstance(raw_fingerprint, Mapping):
            raise ReplayRevalidationCandidateSnapshotError(
                "fingerprint must be an object"
            )
        try:
            fingerprint = ReplayRevalidationFingerprintV1.from_dict(
                cast(Mapping[str, object], raw_fingerprint)
            )
        except ReplayRevalidationError as exc:
            raise ReplayRevalidationCandidateSnapshotError(
                f"invalid candidate fingerprint: {exc}"
            ) from exc
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            candidate_repository_sha=_git_sha(
                value.get("candidate_repository_sha"),
                field="candidate_repository_sha",
            ),
            runtime_material=ReplayRevalidationRuntimeMaterialV1.from_dict(
                cast(Mapping[str, object], raw_material)
            ),
            fingerprint=fingerprint,
        )
        if dict(raw_identity) != result.runtime_identity.canonical_dict():
            raise ReplayRevalidationCandidateSnapshotError(
                "serialized RuntimeIdentity does not match materialized candidate"
            )
        recorded_digest = value.get("snapshot_digest")
        if not isinstance(recorded_digest, str):
            raise ReplayRevalidationCandidateSnapshotError(
                "snapshot_digest must be lowercase sha256"
            )
        try:
            normalized_digest = require_hex_digest(
                recorded_digest,
                field_name="snapshot_digest",
            )
        except ValueError as exc:
            raise ReplayRevalidationCandidateSnapshotError(str(exc)) from exc
        if normalized_digest != recorded_digest:
            raise ReplayRevalidationCandidateSnapshotError(
                "snapshot_digest must be canonical lowercase sha256"
            )
        if recorded_digest != result.snapshot_digest:
            raise ReplayRevalidationCandidateSnapshotError(
                "candidate snapshot digest mismatch"
            )
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationCandidateSnapshotError(
                "candidate snapshot is not canonical"
            )
        return result

    @property
    def repository_change_detection_authority(self) -> bool:
        return False

    @property
    def scheduler_authority(self) -> bool:
        return False

    @property
    def replay_execution_authority(self) -> bool:
        return False

    @property
    def provider_authority(self) -> bool:
        return False

    @property
    def storage_authority(self) -> bool:
        return False

    @property
    def mutable_pointer_authority(self) -> bool:
        return False

    @property
    def product_write_authority(self) -> bool:
        return False

    @property
    def ccl_write_authority(self) -> bool:
        return False

    @property
    def release_authority(self) -> bool:
        return False


def materialize_revalidation_candidate_snapshot_v1(
    *,
    candidate_repository_sha: str,
    runtime_material: ReplayRevalidationRuntimeMaterialV1,
    lrd01i_bundle_digest: str,
    ssc02_manifest_digest: str,
    environment_profile_digests: Sequence[str],
    replay_policy_digest: str,
    migration_registry_digest: str,
    canonicalization_profile_digest: str,
    crypto_profile_digest: str,
    storage_profile_digests: Sequence[str],
) -> ReplayRevalidationCandidateSnapshotV1:
    """Materialize one exact candidate without discovering or executing anything."""
    exact_sha = _git_sha(
        candidate_repository_sha,
        field="candidate_repository_sha",
    )
    if not isinstance(runtime_material, ReplayRevalidationRuntimeMaterialV1):
        raise ReplayRevalidationCandidateSnapshotError(
            "runtime_material must be ReplayRevalidationRuntimeMaterialV1"
        )
    runtime_identity = runtime_material.build_runtime_identity(repository_sha=exact_sha)
    try:
        fingerprint = ReplayRevalidationFingerprintV1.build(
            runtime_identity=runtime_identity,
            lrd01i_bundle_digest=lrd01i_bundle_digest,
            ssc02_manifest_digest=ssc02_manifest_digest,
            environment_profile_digests=environment_profile_digests,
            replay_policy_digest=replay_policy_digest,
            migration_registry_digest=migration_registry_digest,
            canonicalization_profile_digest=canonicalization_profile_digest,
            crypto_profile_digest=crypto_profile_digest,
            storage_profile_digests=storage_profile_digests,
        )
    except ReplayRevalidationError as exc:
        raise ReplayRevalidationCandidateSnapshotError(
            f"cannot materialize LRD-01M fingerprint: {exc}"
        ) from exc
    return ReplayRevalidationCandidateSnapshotV1(
        candidate_repository_sha=exact_sha,
        runtime_material=runtime_material,
        fingerprint=fingerprint,
    )
