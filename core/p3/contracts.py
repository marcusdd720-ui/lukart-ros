"""Shared P3 integrity contracts.

P3 treats canonical bytes, content digests and explicit trust boundaries as
public contracts. These helpers deliberately contain no Product reasoning
logic; they only protect transport, persistence and orchestration boundaries.
"""

from __future__ import annotations

import hashlib
import json
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

_HEX_ALPHABET = frozenset(string.hexdigits.lower())
RUNTIME_IDENTITY_V2 = "lukart.runtime-identity.v2"
RUNTIME_IDENTITY_V3 = "lukart.runtime-identity.v3"


class P3ContractError(ValueError):
    """Fail-closed contract violation at a P3 boundary."""


class TrustLevel(StrEnum):
    UNTRUSTED = "UNTRUSTED"
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    TRUSTED = "TRUSTED"


class ReplayRelation(StrEnum):
    """Exact replay identity relation; never infer IDENTICAL from partial identity."""

    IDENTICAL = "IDENTICAL"
    CROSS_VERSION_COMPARABLE = "CROSS_VERSION_COMPARABLE"
    DIFFERENT = "DIFFERENT"
    INCOMPLETE = "INCOMPLETE"


def require_hex_digest(
    value: str,
    *,
    field_name: str,
    lengths: tuple[int, ...] = (64,),
) -> str:
    normalized = value.strip().lower()
    if len(normalized) not in lengths:
        allowed = "/".join(str(length) for length in lengths)
        raise P3ContractError(f"{field_name} must be a {allowed}-character hex digest")
    if any(character not in _HEX_ALPHABET for character in normalized):
        raise P3ContractError(f"{field_name} must contain hexadecimal characters only")
    return normalized


def _normalize_versioned_identities(
    values: Sequence[str], *, field_name: str
) -> tuple[str, ...]:
    normalized = tuple(sorted({item.strip() for item in values}))
    if any(not item for item in normalized):
        raise P3ContractError(f"{field_name} cannot contain blank identities")
    if any("@" not in item or item.startswith("@") or item.endswith("@") for item in normalized):
        raise P3ContractError(f"{field_name} must use id@version identities")
    return normalized


def _normalize_digests(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                require_hex_digest(item, field_name=field_name)
                for item in values
            }
        )
    )


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Versioned execution identity used by canonical replay/provenance contracts.

    v2 identities remain readable but can never support a v3 exact-replay claim.
    v3 adds dependency, interpreter, platform, project and build-backend identity.
    Missing declarations remain explicit and fail closed as INCOMPLETE.
    """

    code_sha: str
    schema_version: str
    config_digest: str
    corpus_digest: str
    provider_identities: tuple[str, ...] = ()
    plugin_identities: tuple[str, ...] = ()
    input_digests: tuple[str, ...] = ()
    evidence_digests: tuple[str, ...] = ()
    provider_inventory_declared: bool = False
    plugin_inventory_declared: bool = False
    input_inventory_declared: bool = False
    evidence_inventory_declared: bool = False
    identity_schema: str = RUNTIME_IDENTITY_V3
    dependency_lock_digest: str = ""
    python_implementation: str = ""
    python_version: str = ""
    platform_tag: str = ""
    project_version: str = ""
    build_backend: str = ""
    execution_environment_declared: bool = False

    def __post_init__(self) -> None:
        schema_version = self.schema_version.strip()
        identity_schema = self.identity_schema.strip()
        if not schema_version:
            raise P3ContractError("schema_version cannot be blank")
        if identity_schema not in {RUNTIME_IDENTITY_V2, RUNTIME_IDENTITY_V3}:
            raise P3ContractError(f"unsupported runtime identity schema: {identity_schema}")
        code_sha = require_hex_digest(
            self.code_sha,
            field_name="code_sha",
            lengths=(40, 64),
        )
        config_digest = require_hex_digest(
            self.config_digest,
            field_name="config_digest",
        )
        corpus_digest = require_hex_digest(
            self.corpus_digest,
            field_name="corpus_digest",
        )
        providers = _normalize_versioned_identities(
            self.provider_identities,
            field_name="provider identities",
        )
        plugins = _normalize_versioned_identities(
            self.plugin_identities,
            field_name="plugin identities",
        )
        inputs = _normalize_digests(self.input_digests, field_name="input_digest")
        evidence = _normalize_digests(self.evidence_digests, field_name="evidence_digest")

        dependency_lock_digest = self.dependency_lock_digest.strip().lower()
        execution_values = {
            "dependency_lock_digest": dependency_lock_digest,
            "python_implementation": self.python_implementation.strip(),
            "python_version": self.python_version.strip(),
            "platform_tag": self.platform_tag.strip(),
            "project_version": self.project_version.strip(),
            "build_backend": self.build_backend.strip(),
        }
        if identity_schema == RUNTIME_IDENTITY_V2:
            if self.execution_environment_declared or any(execution_values.values()):
                raise P3ContractError("v2 runtime identity cannot contain v3 execution identity")
        elif self.execution_environment_declared:
            missing = sorted(name for name, value in execution_values.items() if not value)
            if missing:
                raise P3ContractError(
                    "declared v3 execution identity is incomplete: " + ", ".join(missing)
                )
            dependency_lock_digest = require_hex_digest(
                dependency_lock_digest,
                field_name="dependency_lock_digest",
            )

        object.__setattr__(self, "code_sha", code_sha)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "config_digest", config_digest)
        object.__setattr__(self, "corpus_digest", corpus_digest)
        object.__setattr__(self, "provider_identities", providers)
        object.__setattr__(self, "plugin_identities", plugins)
        object.__setattr__(self, "input_digests", inputs)
        object.__setattr__(self, "evidence_digests", evidence)
        object.__setattr__(self, "identity_schema", identity_schema)
        object.__setattr__(self, "dependency_lock_digest", dependency_lock_digest)
        for field_name in (
            "python_implementation",
            "python_version",
            "platform_tag",
            "project_version",
            "build_backend",
        ):
            object.__setattr__(self, field_name, execution_values[field_name])

    @property
    def complete_for_replay(self) -> bool:
        return self.identity_schema == RUNTIME_IDENTITY_V3 and all(
            (
                self.provider_inventory_declared,
                self.plugin_inventory_declared,
                self.input_inventory_declared,
                self.evidence_inventory_declared,
                self.execution_environment_declared,
            )
        )

    def incomplete_fields(self) -> tuple[str, ...]:
        flags = {
            "provider_identities": self.provider_inventory_declared,
            "plugin_identities": self.plugin_inventory_declared,
            "input_digests": self.input_inventory_declared,
            "evidence_digests": self.evidence_inventory_declared,
            "execution_environment": (
                self.identity_schema == RUNTIME_IDENTITY_V3
                and self.execution_environment_declared
            ),
        }
        return tuple(sorted(name for name, declared in flags.items() if not declared))

    def canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "identity_schema": self.identity_schema,
            "code_sha": self.code_sha,
            "schema_version": self.schema_version,
            "config_digest": self.config_digest,
            "corpus_digest": self.corpus_digest,
            "provider_identities": list(self.provider_identities),
            "plugin_identities": list(self.plugin_identities),
            "input_digests": list(self.input_digests),
            "evidence_digests": list(self.evidence_digests),
            "inventories_declared": {
                "providers": self.provider_inventory_declared,
                "plugins": self.plugin_inventory_declared,
                "inputs": self.input_inventory_declared,
                "evidence": self.evidence_inventory_declared,
            },
        }
        if self.identity_schema == RUNTIME_IDENTITY_V3:
            declared = dict(payload["inventories_declared"])
            declared["execution_environment"] = self.execution_environment_declared
            payload["inventories_declared"] = declared
            payload["execution_environment"] = {
                "dependency_lock_digest": self.dependency_lock_digest,
                "python_implementation": self.python_implementation,
                "python_version": self.python_version,
                "platform_tag": self.platform_tag,
                "project_version": self.project_version,
                "build_backend": self.build_backend,
            }
        return payload

    def digest(self) -> str:
        return content_digest(self.canonical_dict())

    def differing_fields(self, other: RuntimeIdentity) -> tuple[str, ...]:
        left = self.canonical_dict()
        right = other.canonical_dict()
        keys = set(left) | set(right)
        return tuple(sorted(key for key in keys if left.get(key) != right.get(key)))


def enrich_runtime_identity_v2(
    identity: RuntimeIdentity,
    *,
    dependency_lock_digest: str,
    python_implementation: str,
    python_version: str,
    platform_tag: str,
    project_version: str,
    build_backend: str,
) -> RuntimeIdentity:
    """Create v3 only from explicit evidence; enrichment is not an identical-replay proof."""

    if identity.identity_schema != RUNTIME_IDENTITY_V2:
        raise P3ContractError("runtime identity enrichment requires a v2 source")
    return RuntimeIdentity(
        code_sha=identity.code_sha,
        schema_version=identity.schema_version,
        config_digest=identity.config_digest,
        corpus_digest=identity.corpus_digest,
        provider_identities=identity.provider_identities,
        plugin_identities=identity.plugin_identities,
        input_digests=identity.input_digests,
        evidence_digests=identity.evidence_digests,
        provider_inventory_declared=identity.provider_inventory_declared,
        plugin_inventory_declared=identity.plugin_inventory_declared,
        input_inventory_declared=identity.input_inventory_declared,
        evidence_inventory_declared=identity.evidence_inventory_declared,
        identity_schema=RUNTIME_IDENTITY_V3,
        dependency_lock_digest=dependency_lock_digest,
        python_implementation=python_implementation,
        python_version=python_version,
        platform_tag=platform_tag,
        project_version=project_version,
        build_backend=build_backend,
        execution_environment_declared=True,
    )


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    relation: ReplayRelation
    baseline_identity_digest: str
    candidate_identity_digest: str
    differing_fields: tuple[str, ...]
    migration_path: tuple[str, ...] = ()
    semantic_divergence: bool | None = None
    unresolved: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_hex_digest(
            self.baseline_identity_digest,
            field_name="baseline_identity_digest",
        )
        require_hex_digest(
            self.candidate_identity_digest,
            field_name="candidate_identity_digest",
        )
        if self.relation is ReplayRelation.IDENTICAL and (
            self.differing_fields or self.migration_path or self.unresolved
        ):
            raise P3ContractError("IDENTICAL replay cannot contain differences or unresolved state")
        if (
            self.relation is ReplayRelation.CROSS_VERSION_COMPARABLE
            and len(self.migration_path) < 2
        ):
            raise P3ContractError("cross-version replay requires explicit migration path")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation.value,
            "baseline_identity_digest": self.baseline_identity_digest,
            "candidate_identity_digest": self.candidate_identity_digest,
            "differing_fields": list(self.differing_fields),
            "migration_path": list(self.migration_path),
            "semantic_divergence": self.semantic_divergence,
            "unresolved": list(self.unresolved),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda item: str(item[0]))
        return {str(key): _normalize(item) for key, item in items}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, set | frozenset):
        normalized = [_normalize(item) for item in value]
        return sorted(normalized, key=lambda item: canonical_json(item))
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "canonical_dict"):
        canonical = value.canonical_dict()
        if not isinstance(canonical, Mapping):
            raise P3ContractError("canonical_dict() must return a mapping")
        return _normalize(canonical)
    raise P3ContractError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return deterministic UTF-8 JSON representation for supported values."""

    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_digest(value: object, expected_digest: str) -> None:
    expected = require_hex_digest(expected_digest, field_name="expected_digest")
    actual = content_digest(value)
    if actual != expected:
        raise P3ContractError("content digest mismatch")


def require_unique_nonblank(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in values)
    if any(not item for item in normalized):
        raise P3ContractError(f"{field_name} cannot contain blank values")
    if len(set(normalized)) != len(normalized):
        raise P3ContractError(f"{field_name} cannot contain duplicates")
    return normalized
