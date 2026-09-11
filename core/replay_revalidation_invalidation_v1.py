"""LRD-01M change-triggered replay invalidation and revalidation requirement v1.

This module is a verification-only projection over identities already owned by RuntimeIdentity v3,
LRD-01I, SSC-02, LRD-01K and storage-profile authorities. It does not schedule work, execute a
replay, mutate Product/CCL state, choose cadence, or grant release/certification authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import RuntimeIdentity, content_digest, require_hex_digest

REVALIDATION_FINGERPRINT_SCHEMA_V1 = "lukart.replay-revalidation-fingerprint.v1"
REVALIDATION_DECISION_SCHEMA_V1 = "lukart.replay-revalidation-decision.v1"


class ReplayRevalidationError(ValueError):
    """Fail-closed LRD-01M contract violation."""


class ReplayRevalidationState(StrEnum):
    UNCHANGED = "UNCHANGED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    UNVERIFIABLE = "UNVERIFIABLE"


class ReplayChangeDomain(StrEnum):
    CODE = "CODE"
    SCHEMA = "SCHEMA"
    CONFIG = "CONFIG"
    CORPUS = "CORPUS"
    PROVIDER = "PROVIDER"
    PLUGIN = "PLUGIN"
    INPUT = "INPUT"
    EVIDENCE = "EVIDENCE"
    DEPENDENCY = "DEPENDENCY"
    PYTHON = "PYTHON"
    PLATFORM = "PLATFORM"
    PROJECT_VERSION = "PROJECT_VERSION"
    BUILD = "BUILD"
    PRESERVED_BUNDLE = "PRESERVED_BUNDLE"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    ENVIRONMENT = "ENVIRONMENT"
    REPLAY_POLICY = "REPLAY_POLICY"
    MIGRATION = "MIGRATION"
    CANONICALIZATION = "CANONICALIZATION"
    CRYPTO = "CRYPTO"
    STORAGE = "STORAGE"


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationError(f"{field} must be canonical nonblank text")
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationError(f"{field} must be canonical lowercase sha256")
    return normalized


def _optional_digest(value: object, *, field: str) -> str | None:
    return None if value is None else _digest(value, field=field)


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


def _digest_inventory(
    values: Sequence[object],
    *,
    field: str,
    minimum: int,
) -> tuple[str, ...]:
    parsed = tuple(_digest(value, field=field) for value in values)
    normalized = tuple(sorted(set(parsed)))
    if len(normalized) < minimum:
        raise ReplayRevalidationError(
            f"{field} requires at least {minimum} unique content identities"
        )
    return normalized


def _text_inventory(values: Sequence[object], *, field: str) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field=field) for value in values}))


_FINGERPRINT_KEYS = frozenset(
    {
        "schema",
        "runtime_identity_digest",
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "environment_profile_digests",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
        "storage_profile_digests",
        "fingerprint_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationFingerprintV1:
    """Content-addressed identity of inputs whose change invalidates an old replay PASS."""

    runtime_identity_digest: str
    lrd01i_bundle_digest: str
    ssc02_manifest_digest: str
    environment_profile_digests: tuple[str, ...]
    replay_policy_digest: str
    migration_registry_digest: str
    canonicalization_profile_digest: str
    crypto_profile_digest: str
    storage_profile_digests: tuple[str, ...]
    schema: str = REVALIDATION_FINGERPRINT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_FINGERPRINT_SCHEMA_V1:
            raise ReplayRevalidationError(f"unsupported fingerprint schema: {self.schema}")
        for field in (
            "runtime_identity_digest",
            "lrd01i_bundle_digest",
            "ssc02_manifest_digest",
            "replay_policy_digest",
            "migration_registry_digest",
            "canonicalization_profile_digest",
            "crypto_profile_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field=field))
        object.__setattr__(
            self,
            "environment_profile_digests",
            _digest_inventory(
                self.environment_profile_digests,
                field="environment_profile_digest",
                minimum=2,
            ),
        )
        object.__setattr__(
            self,
            "storage_profile_digests",
            _digest_inventory(
                self.storage_profile_digests,
                field="storage_profile_digest",
                minimum=1,
            ),
        )

    @classmethod
    def build(
        cls,
        *,
        runtime_identity: RuntimeIdentity,
        lrd01i_bundle_digest: str,
        ssc02_manifest_digest: str,
        environment_profile_digests: Sequence[str],
        replay_policy_digest: str,
        migration_registry_digest: str,
        canonicalization_profile_digest: str,
        crypto_profile_digest: str,
        storage_profile_digests: Sequence[str],
    ) -> ReplayRevalidationFingerprintV1:
        if not runtime_identity.complete_for_replay:
            missing = ",".join(runtime_identity.incomplete_fields()) or "runtime_identity_v3"
            raise ReplayRevalidationError(
                "RuntimeIdentity must be complete for replay: " + missing
            )
        return cls(
            runtime_identity_digest=runtime_identity.digest(),
            lrd01i_bundle_digest=lrd01i_bundle_digest,
            ssc02_manifest_digest=ssc02_manifest_digest,
            environment_profile_digests=tuple(environment_profile_digests),
            replay_policy_digest=replay_policy_digest,
            migration_registry_digest=migration_registry_digest,
            canonicalization_profile_digest=canonicalization_profile_digest,
            crypto_profile_digest=crypto_profile_digest,
            storage_profile_digests=tuple(storage_profile_digests),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "runtime_identity_digest": self.runtime_identity_digest,
            "lrd01i_bundle_digest": self.lrd01i_bundle_digest,
            "ssc02_manifest_digest": self.ssc02_manifest_digest,
            "environment_profile_digests": list(self.environment_profile_digests),
            "replay_policy_digest": self.replay_policy_digest,
            "migration_registry_digest": self.migration_registry_digest,
            "canonicalization_profile_digest": self.canonicalization_profile_digest,
            "crypto_profile_digest": self.crypto_profile_digest,
            "storage_profile_digests": list(self.storage_profile_digests),
        }

    @property
    def fingerprint_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "fingerprint_digest": self.fingerprint_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayRevalidationFingerprintV1:
        _strict(value, _FINGERPRINT_KEYS, field="revalidation fingerprint")
        raw_environments = value.get("environment_profile_digests")
        raw_storage = value.get("storage_profile_digests")
        if not isinstance(raw_environments, list) or not isinstance(raw_storage, list):
            raise ReplayRevalidationError("fingerprint identity inventories must be lists")
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            runtime_identity_digest=_digest(
                value.get("runtime_identity_digest"), field="runtime_identity_digest"
            ),
            lrd01i_bundle_digest=_digest(
                value.get("lrd01i_bundle_digest"), field="lrd01i_bundle_digest"
            ),
            ssc02_manifest_digest=_digest(
                value.get("ssc02_manifest_digest"), field="ssc02_manifest_digest"
            ),
            environment_profile_digests=_digest_inventory(
                raw_environments,
                field="environment_profile_digest",
                minimum=2,
            ),
            replay_policy_digest=_digest(
                value.get("replay_policy_digest"), field="replay_policy_digest"
            ),
            migration_registry_digest=_digest(
                value.get("migration_registry_digest"), field="migration_registry_digest"
            ),
            canonicalization_profile_digest=_digest(
                value.get("canonicalization_profile_digest"),
                field="canonicalization_profile_digest",
            ),
            crypto_profile_digest=_digest(
                value.get("crypto_profile_digest"), field="crypto_profile_digest"
            ),
            storage_profile_digests=_digest_inventory(
                raw_storage,
                field="storage_profile_digest",
                minimum=1,
            ),
        )
        expected = _digest(value.get("fingerprint_digest"), field="fingerprint_digest")
        if result.fingerprint_digest != expected:
            raise ReplayRevalidationError("fingerprint_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationError("revalidation fingerprint is not canonical")
        return result


_DECISION_KEYS = frozenset(
    {
        "schema",
        "baseline_fingerprint_digest",
        "candidate_fingerprint_digest",
        "state",
        "changed_domains",
        "changed_fields",
        "violations",
        "baseline_replay_reusable",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "decision_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationDecisionV1:
    baseline_fingerprint_digest: str | None
    candidate_fingerprint_digest: str
    state: ReplayRevalidationState
    changed_domains: tuple[ReplayChangeDomain, ...]
    changed_fields: tuple[str, ...]
    violations: tuple[str, ...]
    schema: str = REVALIDATION_DECISION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_DECISION_SCHEMA_V1:
            raise ReplayRevalidationError(f"unsupported decision schema: {self.schema}")
        object.__setattr__(
            self,
            "baseline_fingerprint_digest",
            _optional_digest(
                self.baseline_fingerprint_digest,
                field="baseline_fingerprint_digest",
            ),
        )
        object.__setattr__(
            self,
            "candidate_fingerprint_digest",
            _digest(self.candidate_fingerprint_digest, field="candidate_fingerprint_digest"),
        )
        if not isinstance(self.state, ReplayRevalidationState):
            raise ReplayRevalidationError("unknown replay revalidation state")
        if any(not isinstance(item, ReplayChangeDomain) for item in self.changed_domains):
            raise ReplayRevalidationError("changed_domains contains an unknown domain")
        domains = tuple(sorted(set(self.changed_domains), key=lambda item: item.value))
        fields = _text_inventory(self.changed_fields, field="changed_field")
        violations = _text_inventory(self.violations, field="violation")
        object.__setattr__(self, "changed_domains", domains)
        object.__setattr__(self, "changed_fields", fields)
        object.__setattr__(self, "violations", violations)
        if self.state is ReplayRevalidationState.UNCHANGED:
            if self.baseline_fingerprint_digest is None or domains or fields or violations:
                raise ReplayRevalidationError(
                    "UNCHANGED decision cannot contain change/error evidence"
                )
        elif self.state is ReplayRevalidationState.REVALIDATION_REQUIRED:
            if self.baseline_fingerprint_digest is None or not domains or not fields or violations:
                raise ReplayRevalidationError(
                    "REVALIDATION_REQUIRED needs baseline and exact change evidence"
                )
        elif not violations or domains or fields:
            raise ReplayRevalidationError(
                "UNVERIFIABLE decision requires violations and no asserted change inventory"
            )

    @property
    def baseline_replay_reusable(self) -> bool:
        return self.state is ReplayRevalidationState.UNCHANGED

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "baseline_fingerprint_digest": self.baseline_fingerprint_digest,
            "candidate_fingerprint_digest": self.candidate_fingerprint_digest,
            "state": self.state.value,
            "changed_domains": [item.value for item in self.changed_domains],
            "changed_fields": list(self.changed_fields),
            "violations": list(self.violations),
            "baseline_replay_reusable": self.baseline_replay_reusable,
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
        }

    @property
    def decision_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "decision_digest": self.decision_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayRevalidationDecisionV1:
        _strict(value, _DECISION_KEYS, field="revalidation decision")
        for authority in (
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationError(f"{authority} must remain false")
        raw_domains = value.get("changed_domains")
        raw_fields = value.get("changed_fields")
        raw_violations = value.get("violations")
        if not all(isinstance(item, list) for item in (raw_domains, raw_fields, raw_violations)):
            raise ReplayRevalidationError("decision inventories must be lists")
        try:
            state = ReplayRevalidationState(_text(value.get("state"), field="state"))
            domains = tuple(
                ReplayChangeDomain(_text(item, field="changed_domain"))
                for item in raw_domains
            )
        except ValueError as exc:
            raise ReplayRevalidationError("unknown revalidation state or change domain") from exc
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            baseline_fingerprint_digest=_optional_digest(
                value.get("baseline_fingerprint_digest"),
                field="baseline_fingerprint_digest",
            ),
            candidate_fingerprint_digest=_digest(
                value.get("candidate_fingerprint_digest"),
                field="candidate_fingerprint_digest",
            ),
            state=state,
            changed_domains=domains,
            changed_fields=_text_inventory(raw_fields, field="changed_field"),
            violations=_text_inventory(raw_violations, field="violation"),
        )
        if value.get("baseline_replay_reusable") is not result.baseline_replay_reusable:
            raise ReplayRevalidationError("baseline_replay_reusable mismatch")
        expected = _digest(value.get("decision_digest"), field="decision_digest")
        if result.decision_digest != expected:
            raise ReplayRevalidationError("decision_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationError("revalidation decision is not canonical")
        return result


def _runtime_change_evidence(
    baseline: RuntimeIdentity,
    candidate: RuntimeIdentity,
) -> tuple[tuple[ReplayChangeDomain, ...], tuple[str, ...]]:
    comparisons = (
        ("runtime.code_sha", ReplayChangeDomain.CODE, baseline.code_sha, candidate.code_sha),
        (
            "runtime.schema_version",
            ReplayChangeDomain.SCHEMA,
            baseline.schema_version,
            candidate.schema_version,
        ),
        (
            "runtime.config_digest",
            ReplayChangeDomain.CONFIG,
            baseline.config_digest,
            candidate.config_digest,
        ),
        (
            "runtime.corpus_digest",
            ReplayChangeDomain.CORPUS,
            baseline.corpus_digest,
            candidate.corpus_digest,
        ),
        (
            "runtime.provider_identities",
            ReplayChangeDomain.PROVIDER,
            baseline.provider_identities,
            candidate.provider_identities,
        ),
        (
            "runtime.plugin_identities",
            ReplayChangeDomain.PLUGIN,
            baseline.plugin_identities,
            candidate.plugin_identities,
        ),
        (
            "runtime.input_digests",
            ReplayChangeDomain.INPUT,
            baseline.input_digests,
            candidate.input_digests,
        ),
        (
            "runtime.evidence_digests",
            ReplayChangeDomain.EVIDENCE,
            baseline.evidence_digests,
            candidate.evidence_digests,
        ),
        (
            "runtime.dependency_lock_digest",
            ReplayChangeDomain.DEPENDENCY,
            baseline.dependency_lock_digest,
            candidate.dependency_lock_digest,
        ),
        (
            "runtime.python_implementation",
            ReplayChangeDomain.PYTHON,
            baseline.python_implementation,
            candidate.python_implementation,
        ),
        (
            "runtime.python_version",
            ReplayChangeDomain.PYTHON,
            baseline.python_version,
            candidate.python_version,
        ),
        (
            "runtime.platform_tag",
            ReplayChangeDomain.PLATFORM,
            baseline.platform_tag,
            candidate.platform_tag,
        ),
        (
            "runtime.project_version",
            ReplayChangeDomain.PROJECT_VERSION,
            baseline.project_version,
            candidate.project_version,
        ),
        (
            "runtime.build_backend",
            ReplayChangeDomain.BUILD,
            baseline.build_backend,
            candidate.build_backend,
        ),
    )
    domains: set[ReplayChangeDomain] = set()
    fields: list[str] = []
    for field, domain, old, new in comparisons:
        if old != new:
            domains.add(domain)
            fields.append(field)
    return tuple(sorted(domains, key=lambda item: item.value)), tuple(sorted(fields))


def evaluate_revalidation_requirement_v1(
    *,
    baseline: ReplayRevalidationFingerprintV1 | None,
    candidate: ReplayRevalidationFingerprintV1,
    baseline_runtime_identity: RuntimeIdentity | None,
    candidate_runtime_identity: RuntimeIdentity,
) -> ReplayRevalidationDecisionV1:
    """Fail closed when an old replay PASS lacks a matching current dependency fingerprint."""
    candidate_runtime_digest = candidate_runtime_identity.digest()
    if candidate.runtime_identity_digest != candidate_runtime_digest:
        raise ReplayRevalidationError("candidate RuntimeIdentity substitution detected")
    if not candidate_runtime_identity.complete_for_replay:
        return ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=(
                None if baseline is None else baseline.fingerprint_digest
            ),
            candidate_fingerprint_digest=candidate.fingerprint_digest,
            state=ReplayRevalidationState.UNVERIFIABLE,
            changed_domains=(),
            changed_fields=(),
            violations=("candidate_runtime_identity_incomplete",),
        )
    if baseline is None or baseline_runtime_identity is None:
        return ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=None,
            candidate_fingerprint_digest=candidate.fingerprint_digest,
            state=ReplayRevalidationState.UNVERIFIABLE,
            changed_domains=(),
            changed_fields=(),
            violations=("baseline_revalidation_fingerprint_missing",),
        )
    if baseline.runtime_identity_digest != baseline_runtime_identity.digest():
        raise ReplayRevalidationError("baseline RuntimeIdentity substitution detected")
    if not baseline_runtime_identity.complete_for_replay:
        return ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=baseline.fingerprint_digest,
            candidate_fingerprint_digest=candidate.fingerprint_digest,
            state=ReplayRevalidationState.UNVERIFIABLE,
            changed_domains=(),
            changed_fields=(),
            violations=("baseline_runtime_identity_incomplete",),
        )

    domains, fields = _runtime_change_evidence(
        baseline_runtime_identity,
        candidate_runtime_identity,
    )
    domain_set = set(domains)
    field_list = list(fields)
    fingerprint_comparisons = (
        (
            "lrd01i_bundle_digest",
            ReplayChangeDomain.PRESERVED_BUNDLE,
            baseline.lrd01i_bundle_digest,
            candidate.lrd01i_bundle_digest,
        ),
        (
            "ssc02_manifest_digest",
            ReplayChangeDomain.SUPPLY_CHAIN,
            baseline.ssc02_manifest_digest,
            candidate.ssc02_manifest_digest,
        ),
        (
            "environment_profile_digests",
            ReplayChangeDomain.ENVIRONMENT,
            baseline.environment_profile_digests,
            candidate.environment_profile_digests,
        ),
        (
            "replay_policy_digest",
            ReplayChangeDomain.REPLAY_POLICY,
            baseline.replay_policy_digest,
            candidate.replay_policy_digest,
        ),
        (
            "migration_registry_digest",
            ReplayChangeDomain.MIGRATION,
            baseline.migration_registry_digest,
            candidate.migration_registry_digest,
        ),
        (
            "canonicalization_profile_digest",
            ReplayChangeDomain.CANONICALIZATION,
            baseline.canonicalization_profile_digest,
            candidate.canonicalization_profile_digest,
        ),
        (
            "crypto_profile_digest",
            ReplayChangeDomain.CRYPTO,
            baseline.crypto_profile_digest,
            candidate.crypto_profile_digest,
        ),
        (
            "storage_profile_digests",
            ReplayChangeDomain.STORAGE,
            baseline.storage_profile_digests,
            candidate.storage_profile_digests,
        ),
    )
    for field, domain, old, new in fingerprint_comparisons:
        if old != new:
            domain_set.add(domain)
            field_list.append(field)
    if not field_list:
        return ReplayRevalidationDecisionV1(
            baseline_fingerprint_digest=baseline.fingerprint_digest,
            candidate_fingerprint_digest=candidate.fingerprint_digest,
            state=ReplayRevalidationState.UNCHANGED,
            changed_domains=(),
            changed_fields=(),
            violations=(),
        )
    return ReplayRevalidationDecisionV1(
        baseline_fingerprint_digest=baseline.fingerprint_digest,
        candidate_fingerprint_digest=candidate.fingerprint_digest,
        state=ReplayRevalidationState.REVALIDATION_REQUIRED,
        changed_domains=tuple(sorted(domain_set, key=lambda item: item.value)),
        changed_fields=tuple(sorted(set(field_list))),
        violations=(),
    )


def verify_revalidation_decision_v1(
    decision: ReplayRevalidationDecisionV1,
    *,
    baseline: ReplayRevalidationFingerprintV1 | None,
    candidate: ReplayRevalidationFingerprintV1,
    baseline_runtime_identity: RuntimeIdentity | None,
    candidate_runtime_identity: RuntimeIdentity,
) -> str:
    """Recompute one decision from exact inputs and return its content identity."""
    expected = evaluate_revalidation_requirement_v1(
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime_identity,
        candidate_runtime_identity=candidate_runtime_identity,
    )
    if decision.canonical_dict() != expected.canonical_dict():
        raise ReplayRevalidationError("revalidation decision evidence mismatch")
    return decision.decision_digest
