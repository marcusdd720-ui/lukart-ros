"""PHX-05 exact Case Replay v2 over CCL, Epistemic v2 and Trust Graph v1.

Replay is a verification artifact, never another truth store. The bundle carries the
canonical case history plus exact policy/runtime/migration identities needed to rebuild
Epistemic and Trust Graph projections offline.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from core.case_ledger.contracts import (
    LEDGER_BUNDLE_SCHEMA_V1,
    LEDGER_EVENT_SCHEMA_V1,
    CaseId,
    CaseLedgerBundle,
    ContentAddress,
)
from core.p3.contracts import (
    ReplayRelation,
    RuntimeIdentity,
    canonical_json,
)
from core.p3.versioning import CaseMigrationRegistry
from knowledge.epistemic_assertions import (
    ASSERTION_SCHEMA_V2,
    EPISTEMIC_POLICY_SCHEMA_V2,
    EPISTEMIC_PROJECTION_SCHEMA_V2,
    EpistemicPolicyV2,
    EpistemicProjectionV2,
)
from knowledge.evidence_trust_graph import (
    TRUST_GRAPH_SCHEMA_V1,
    TRUST_POLICY_SCHEMA_V1,
    EvidenceTrustGraph,
    TrustEdgeType,
    TrustPolicyV1,
)

CASE_REPLAY_MANIFEST_SCHEMA_V2 = "lukart.case-replay-manifest.v2"
CASE_REPLAY_BUNDLE_SCHEMA_V2 = "lukart.case-replay-bundle.v2"
CASE_REPLAY_COMPARISON_SCHEMA_V2 = "lukart.case-replay-comparison.v2"

_RUNTIME_KEYS = frozenset(
    {
        "identity_schema",
        "code_sha",
        "schema_version",
        "config_digest",
        "corpus_digest",
        "provider_identities",
        "plugin_identities",
        "input_digests",
        "evidence_digests",
        "inventories_declared",
        "execution_environment",
    }
)
_RUNTIME_DECLARATION_KEYS = frozenset(
    {"providers", "plugins", "inputs", "evidence", "execution_environment"}
)
_RUNTIME_EXECUTION_KEYS = frozenset(
    {
        "dependency_lock_digest",
        "python_implementation",
        "python_version",
        "platform_tag",
        "project_version",
        "build_backend",
    }
)
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "ledger_head",
        "ledger_bundle_digest",
        "epistemic_projection_identity",
        "trust_graph_identity",
        "epistemic_policy_identity",
        "trust_policy_identity",
        "runtime_identity_digest",
        "migration_registry_digest",
        "case_schema_version",
        "schema_identities",
        "evidence_digests",
        "manifest_identity",
    }
)
_BUNDLE_KEYS = frozenset(
    {
        "schema",
        "manifest",
        "ledger_bundle",
        "runtime_identity",
        "migration_registry",
        "epistemic_policy",
        "trust_policy",
        "bundle_identity",
    }
)
_REGISTRY_KEYS = frozenset({"schema", "steps"})
_REGISTRY_STEP_KEYS = frozenset({"source_version", "target_version"})


class CaseReplayV2Error(ValueError):
    """Fail-closed Case Replay v2 contract violation."""


def _copy_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise CaseReplayV2Error(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise CaseReplayV2Error(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise CaseReplayV2Error(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _require_exact_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    missing = tuple(sorted(expected - actual))
    unknown = tuple(sorted(actual - expected))
    if not missing and not unknown:
        return
    details: list[str] = []
    if missing:
        details.append("missing=" + ",".join(missing))
    if unknown:
        details.append("unknown=" + ",".join(unknown))
    raise CaseReplayV2Error(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise CaseReplayV2Error(f"{field_name} must be a content-address object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise CaseReplayV2Error(str(exc)) from exc


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CaseReplayV2Error(f"{field_name} must be a sequence")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise CaseReplayV2Error(f"{field_name} must contain nonblank strings")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise CaseReplayV2Error(f"{field_name} must contain unique values")
    return tuple(sorted(result))


def _runtime_from_snapshot(value: Mapping[str, object]) -> RuntimeIdentity:
    raw = _copy_mapping(value, field_name="runtime identity")
    _require_exact_keys(raw, expected=_RUNTIME_KEYS, field_name="runtime identity")
    declared = raw.get("inventories_declared")
    execution = raw.get("execution_environment")
    if not isinstance(declared, Mapping) or not isinstance(execution, Mapping):
        raise CaseReplayV2Error("runtime identity declarations are incomplete")
    declared_mapping = cast(Mapping[str, object], declared)
    execution_mapping = cast(Mapping[str, object], execution)
    _require_exact_keys(
        declared_mapping,
        expected=_RUNTIME_DECLARATION_KEYS,
        field_name="runtime declarations",
    )
    _require_exact_keys(
        execution_mapping,
        expected=_RUNTIME_EXECUTION_KEYS,
        field_name="runtime execution environment",
    )

    def sequence(name: str) -> tuple[str, ...]:
        return _string_sequence(raw.get(name), field_name=name)

    def declared_flag(name: str) -> bool:
        flag = declared_mapping.get(name)
        if not isinstance(flag, bool):
            raise CaseReplayV2Error(f"runtime declaration {name} must be boolean")
        return flag

    def execution_text(name: str) -> str:
        item = execution_mapping.get(name)
        if not isinstance(item, str) or not item.strip():
            raise CaseReplayV2Error(f"runtime execution field {name} is incomplete")
        return item

    identity_schema = raw.get("identity_schema")
    code_sha = raw.get("code_sha")
    schema_version = raw.get("schema_version")
    config_digest = raw.get("config_digest")
    corpus_digest = raw.get("corpus_digest")
    required = (identity_schema, code_sha, schema_version, config_digest, corpus_digest)
    if not all(isinstance(item, str) for item in required):
        raise CaseReplayV2Error("runtime identity core fields are invalid")

    identity = RuntimeIdentity(
        code_sha=cast(str, code_sha),
        schema_version=cast(str, schema_version),
        config_digest=cast(str, config_digest),
        corpus_digest=cast(str, corpus_digest),
        provider_identities=sequence("provider_identities"),
        plugin_identities=sequence("plugin_identities"),
        input_digests=sequence("input_digests"),
        evidence_digests=sequence("evidence_digests"),
        provider_inventory_declared=declared_flag("providers"),
        plugin_inventory_declared=declared_flag("plugins"),
        input_inventory_declared=declared_flag("inputs"),
        evidence_inventory_declared=declared_flag("evidence"),
        identity_schema=cast(str, identity_schema),
        dependency_lock_digest=execution_text("dependency_lock_digest"),
        python_implementation=execution_text("python_implementation"),
        python_version=execution_text("python_version"),
        platform_tag=execution_text("platform_tag"),
        project_version=execution_text("project_version"),
        build_backend=execution_text("build_backend"),
        execution_environment_declared=declared_flag("execution_environment"),
    )
    if not identity.complete_for_replay:
        raise CaseReplayV2Error(
            "runtime identity is incomplete for exact replay: "
            + ", ".join(identity.incomplete_fields())
        )
    return identity


def _parse_epistemic_policy(value: Mapping[str, object]) -> EpistemicPolicyV2:
    raw = _copy_mapping(value, field_name="epistemic policy")
    event_types = _string_sequence(
        raw.get("fact_evidence_event_types"),
        field_name="fact_evidence_event_types",
    )
    identity = _address(raw.get("policy_identity"), field_name="epistemic policy identity")
    policy = EpistemicPolicyV2(
        fact_evidence_event_types=event_types,
        policy_identity=identity,
    )
    if raw != json.loads(canonical_json(policy.canonical_dict())):
        raise CaseReplayV2Error("epistemic policy snapshot does not match canonical policy")
    return policy


def _parse_trust_policy(value: Mapping[str, object]) -> TrustPolicyV1:
    raw = _copy_mapping(value, field_name="trust policy")
    raw_edges = _string_sequence(
        raw.get("allowed_explicit_edges"),
        field_name="allowed_explicit_edges",
    )
    try:
        edges = tuple(TrustEdgeType(item) for item in raw_edges)
    except ValueError as exc:
        raise CaseReplayV2Error("trust policy contains unknown edge type") from exc
    max_nodes = raw.get("max_nodes")
    max_edges = raw.get("max_edges")
    if (
        not isinstance(max_nodes, int)
        or isinstance(max_nodes, bool)
        or not isinstance(max_edges, int)
        or isinstance(max_edges, bool)
    ):
        raise CaseReplayV2Error("trust policy graph bounds must be integers")
    policy = TrustPolicyV1(
        allowed_explicit_edges=edges,
        max_nodes=max_nodes,
        max_edges=max_edges,
        policy_identity=_address(
            raw.get("policy_identity"),
            field_name="trust policy identity",
        ),
    )
    if raw != json.loads(canonical_json(policy.canonical_dict())):
        raise CaseReplayV2Error("trust policy snapshot does not match canonical policy")
    return policy


def _validate_registry_snapshot(value: Mapping[str, object]) -> dict[str, object]:
    raw = _copy_mapping(value, field_name="migration registry")
    _require_exact_keys(raw, expected=_REGISTRY_KEYS, field_name="migration registry")
    if raw.get("schema") != "lukart.case-migration-registry.v1":
        raise CaseReplayV2Error("unsupported migration registry snapshot schema")
    steps = raw.get("steps")
    if not isinstance(steps, list):
        raise CaseReplayV2Error("migration registry steps must be a list")

    canonical_steps: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(steps):
        if not isinstance(item, Mapping):
            raise CaseReplayV2Error(f"migration registry step {index} must be an object")
        step = _copy_mapping(
            cast(Mapping[str, object], item),
            field_name=f"migration registry step {index}",
        )
        _require_exact_keys(
            step,
            expected=_REGISTRY_STEP_KEYS,
            field_name=f"migration registry step {index}",
        )
        source = step.get("source_version")
        target = step.get("target_version")
        if not isinstance(source, str) or not isinstance(target, str):
            raise CaseReplayV2Error("migration registry versions must be strings")
        source = source.strip()
        target = target.strip()
        if not source or not target or source == target:
            raise CaseReplayV2Error("migration registry contains invalid version pair")
        pair = (source, target)
        if pair in seen:
            raise CaseReplayV2Error("migration registry contains duplicate version pair")
        seen.add(pair)
        canonical_steps.append(
            {"source_version": source, "target_version": target}
        )

    expected_steps = sorted(
        canonical_steps,
        key=lambda item: (item["source_version"], item["target_version"]),
    )
    if canonical_steps != expected_steps or steps != canonical_steps:
        raise CaseReplayV2Error("migration registry steps are not canonical and sorted")
    return raw


@dataclass(frozen=True, slots=True)
class CaseReplayManifestV2:
    case_id: CaseId
    ledger_head: ContentAddress | None
    ledger_bundle_digest: ContentAddress
    epistemic_projection_identity: ContentAddress
    trust_graph_identity: ContentAddress
    epistemic_policy_identity: ContentAddress
    trust_policy_identity: ContentAddress
    runtime_identity_digest: ContentAddress
    migration_registry_digest: ContentAddress
    case_schema_version: str
    schema_identities: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    manifest_identity: ContentAddress
    schema: str = CASE_REPLAY_MANIFEST_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != CASE_REPLAY_MANIFEST_SCHEMA_V2:
            raise CaseReplayV2Error(f"unsupported replay manifest schema: {self.schema}")
        if not self.case_schema_version.strip():
            raise CaseReplayV2Error("case schema version cannot be blank")
        if not self.schema_identities:
            raise CaseReplayV2Error("replay manifest requires schema identities")
        if tuple(sorted(set(self.schema_identities))) != self.schema_identities:
            raise CaseReplayV2Error("schema identities must be unique and sorted")
        if tuple(sorted(set(self.evidence_digests))) != self.evidence_digests:
            raise CaseReplayV2Error("evidence digests must be unique and sorted")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        ledger_bundle: CaseLedgerBundle,
        epistemic_projection: EpistemicProjectionV2,
        trust_graph: EvidenceTrustGraph,
        epistemic_policy: EpistemicPolicyV2,
        trust_policy: TrustPolicyV1,
        runtime_identity: RuntimeIdentity,
        migration_registry: CaseMigrationRegistry,
    ) -> CaseReplayManifestV2:
        if not runtime_identity.complete_for_replay:
            raise CaseReplayV2Error(
                "runtime identity is incomplete for exact replay: "
                + ", ".join(runtime_identity.incomplete_fields())
            )
        ledger_bundle.verify()
        epistemic_projection.verify()
        trust_graph.verify()
        if ledger_bundle.case_id != case_id:
            raise CaseReplayV2Error("ledger bundle belongs to another case")
        if epistemic_projection.case_id != case_id or trust_graph.case_id != case_id:
            raise CaseReplayV2Error("replay projections belong to another case")
        head = ledger_bundle.head_event_id
        if epistemic_projection.ledger_head != head or trust_graph.ledger_head != head:
            raise CaseReplayV2Error("replay projection head does not match ledger bundle")
        if trust_graph.epistemic_projection_identity != epistemic_projection.projection_identity:
            raise CaseReplayV2Error("trust graph is not bound to supplied epistemic projection")

        schema_identities = tuple(
            sorted(
                {
                    LEDGER_BUNDLE_SCHEMA_V1,
                    LEDGER_EVENT_SCHEMA_V1,
                    ASSERTION_SCHEMA_V2,
                    EPISTEMIC_POLICY_SCHEMA_V2,
                    EPISTEMIC_PROJECTION_SCHEMA_V2,
                    TRUST_POLICY_SCHEMA_V1,
                    TRUST_GRAPH_SCHEMA_V1,
                    runtime_identity.identity_schema,
                    runtime_identity.schema_version,
                }
            )
        )
        evidence_digests = tuple(sorted(runtime_identity.evidence_digests))
        registry_address = ContentAddress.for_value(migration_registry.canonical_dict())
        body = cls._body(
            case_id=case_id,
            ledger_head=head,
            ledger_bundle_digest=ledger_bundle.bundle_digest,
            epistemic_projection_identity=epistemic_projection.projection_identity,
            trust_graph_identity=trust_graph.graph_identity,
            epistemic_policy_identity=epistemic_policy.policy_identity,
            trust_policy_identity=trust_policy.policy_identity,
            runtime_identity_digest=ContentAddress.for_value(runtime_identity.canonical_dict()),
            migration_registry_digest=registry_address,
            case_schema_version=runtime_identity.schema_version,
            schema_identities=schema_identities,
            evidence_digests=evidence_digests,
        )
        return cls(
            case_id=case_id,
            ledger_head=head,
            ledger_bundle_digest=ledger_bundle.bundle_digest,
            epistemic_projection_identity=epistemic_projection.projection_identity,
            trust_graph_identity=trust_graph.graph_identity,
            epistemic_policy_identity=epistemic_policy.policy_identity,
            trust_policy_identity=trust_policy.policy_identity,
            runtime_identity_digest=ContentAddress.for_value(runtime_identity.canonical_dict()),
            migration_registry_digest=registry_address,
            case_schema_version=runtime_identity.schema_version,
            schema_identities=schema_identities,
            evidence_digests=evidence_digests,
            manifest_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        case_id: CaseId,
        ledger_head: ContentAddress | None,
        ledger_bundle_digest: ContentAddress,
        epistemic_projection_identity: ContentAddress,
        trust_graph_identity: ContentAddress,
        epistemic_policy_identity: ContentAddress,
        trust_policy_identity: ContentAddress,
        runtime_identity_digest: ContentAddress,
        migration_registry_digest: ContentAddress,
        case_schema_version: str,
        schema_identities: tuple[str, ...],
        evidence_digests: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "schema": CASE_REPLAY_MANIFEST_SCHEMA_V2,
            "case_id": case_id.value,
            "ledger_head": ledger_head.canonical_dict() if ledger_head else None,
            "ledger_bundle_digest": ledger_bundle_digest.canonical_dict(),
            "epistemic_projection_identity": epistemic_projection_identity.canonical_dict(),
            "trust_graph_identity": trust_graph_identity.canonical_dict(),
            "epistemic_policy_identity": epistemic_policy_identity.canonical_dict(),
            "trust_policy_identity": trust_policy_identity.canonical_dict(),
            "runtime_identity_digest": runtime_identity_digest.canonical_dict(),
            "migration_registry_digest": migration_registry_digest.canonical_dict(),
            "case_schema_version": case_schema_version,
            "schema_identities": list(schema_identities),
            "evidence_digests": list(evidence_digests),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CaseReplayManifestV2:
        raw = _copy_mapping(value, field_name="replay manifest")
        _require_exact_keys(raw, expected=_MANIFEST_KEYS, field_name="replay manifest")
        schema = raw.get("schema")
        case_id = raw.get("case_id")
        case_schema_version = raw.get("case_schema_version")
        if not all(isinstance(item, str) for item in (schema, case_id, case_schema_version)):
            raise CaseReplayV2Error("invalid replay manifest identity fields")
        raw_head = raw.get("ledger_head")
        head = None if raw_head is None else _address(raw_head, field_name="ledger_head")
        return cls(
            case_id=CaseId(cast(str, case_id)),
            ledger_head=head,
            ledger_bundle_digest=_address(
                raw.get("ledger_bundle_digest"),
                field_name="ledger_bundle_digest",
            ),
            epistemic_projection_identity=_address(
                raw.get("epistemic_projection_identity"),
                field_name="epistemic_projection_identity",
            ),
            trust_graph_identity=_address(
                raw.get("trust_graph_identity"),
                field_name="trust_graph_identity",
            ),
            epistemic_policy_identity=_address(
                raw.get("epistemic_policy_identity"),
                field_name="epistemic_policy_identity",
            ),
            trust_policy_identity=_address(
                raw.get("trust_policy_identity"),
                field_name="trust_policy_identity",
            ),
            runtime_identity_digest=_address(
                raw.get("runtime_identity_digest"),
                field_name="runtime_identity_digest",
            ),
            migration_registry_digest=_address(
                raw.get("migration_registry_digest"),
                field_name="migration_registry_digest",
            ),
            case_schema_version=cast(str, case_schema_version),
            schema_identities=_string_sequence(
                raw.get("schema_identities"),
                field_name="schema_identities",
            ),
            evidence_digests=_string_sequence(
                raw.get("evidence_digests"),
                field_name="evidence_digests",
            ),
            manifest_identity=_address(
                raw.get("manifest_identity"),
                field_name="manifest_identity",
            ),
            schema=cast(str, schema),
        )

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            case_id=self.case_id,
            ledger_head=self.ledger_head,
            ledger_bundle_digest=self.ledger_bundle_digest,
            epistemic_projection_identity=self.epistemic_projection_identity,
            trust_graph_identity=self.trust_graph_identity,
            epistemic_policy_identity=self.epistemic_policy_identity,
            trust_policy_identity=self.trust_policy_identity,
            runtime_identity_digest=self.runtime_identity_digest,
            migration_registry_digest=self.migration_registry_digest,
            case_schema_version=self.case_schema_version,
            schema_identities=self.schema_identities,
            evidence_digests=self.evidence_digests,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "manifest_identity": self.manifest_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.manifest_identity != ContentAddress.for_value(self.canonical_body()):
            raise CaseReplayV2Error("replay manifest content-address mismatch")


@dataclass(frozen=True, slots=True)
class CaseReplayVerificationV2:
    manifest_identity: ContentAddress
    ledger_head: ContentAddress | None
    epistemic_projection_identity: ContentAddress
    trust_graph_identity: ContentAddress
    runtime_identity_digest: ContentAddress


@dataclass(frozen=True, slots=True)
class CaseReplayBundleV2:
    manifest: CaseReplayManifestV2
    ledger_bundle: CaseLedgerBundle
    runtime_identity: Mapping[str, object]
    migration_registry: Mapping[str, object]
    epistemic_policy: Mapping[str, object]
    trust_policy: Mapping[str, object]
    bundle_identity: ContentAddress
    schema: str = CASE_REPLAY_BUNDLE_SCHEMA_V2

    @classmethod
    def build(
        cls,
        *,
        ledger_bundle: CaseLedgerBundle,
        runtime_identity: RuntimeIdentity,
        migration_registry: CaseMigrationRegistry,
        epistemic_policy: EpistemicPolicyV2,
        trust_policy: TrustPolicyV1,
    ) -> CaseReplayBundleV2:
        if not runtime_identity.complete_for_replay:
            raise CaseReplayV2Error("runtime identity is incomplete for exact replay")
        events = ledger_bundle.events
        epistemic = EpistemicProjectionV2.build(
            case_id=ledger_bundle.case_id,
            events=events,
            policy=epistemic_policy,
        )
        trust = EvidenceTrustGraph.build(
            case_id=ledger_bundle.case_id,
            events=events,
            epistemic_projection=epistemic,
            policy=trust_policy,
        )
        manifest = CaseReplayManifestV2.build(
            case_id=ledger_bundle.case_id,
            ledger_bundle=ledger_bundle,
            epistemic_projection=epistemic,
            trust_graph=trust,
            epistemic_policy=epistemic_policy,
            trust_policy=trust_policy,
            runtime_identity=runtime_identity,
            migration_registry=migration_registry,
        )
        runtime_snapshot = _copy_mapping(
            runtime_identity.canonical_dict(),
            field_name="runtime identity",
        )
        registry_snapshot = _copy_mapping(
            migration_registry.canonical_dict(),
            field_name="migration registry",
        )
        epistemic_snapshot = _copy_mapping(
            epistemic_policy.canonical_dict(),
            field_name="epistemic policy",
        )
        trust_snapshot = _copy_mapping(
            trust_policy.canonical_dict(),
            field_name="trust policy",
        )
        body = cls._body(
            manifest=manifest,
            ledger_bundle=ledger_bundle,
            runtime_identity=runtime_snapshot,
            migration_registry=registry_snapshot,
            epistemic_policy=epistemic_snapshot,
            trust_policy=trust_snapshot,
        )
        return cls(
            manifest=manifest,
            ledger_bundle=ledger_bundle,
            runtime_identity=runtime_snapshot,
            migration_registry=registry_snapshot,
            epistemic_policy=epistemic_snapshot,
            trust_policy=trust_snapshot,
            bundle_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        manifest: CaseReplayManifestV2,
        ledger_bundle: CaseLedgerBundle,
        runtime_identity: Mapping[str, object],
        migration_registry: Mapping[str, object],
        epistemic_policy: Mapping[str, object],
        trust_policy: Mapping[str, object],
    ) -> dict[str, object]:
        return {
            "schema": CASE_REPLAY_BUNDLE_SCHEMA_V2,
            "manifest": manifest.canonical_dict(),
            "ledger_bundle": ledger_bundle.canonical_dict(),
            "runtime_identity": dict(runtime_identity),
            "migration_registry": dict(migration_registry),
            "epistemic_policy": dict(epistemic_policy),
            "trust_policy": dict(trust_policy),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            manifest=self.manifest,
            ledger_bundle=self.ledger_bundle,
            runtime_identity=self.runtime_identity,
            migration_registry=self.migration_registry,
            epistemic_policy=self.epistemic_policy,
            trust_policy=self.trust_policy,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "bundle_identity": self.bundle_identity.canonical_dict(),
        }

    def verify(self) -> CaseReplayVerificationV2:
        verification = verify_case_replay_bundle(self.canonical_dict())
        if self.bundle_identity != ContentAddress.for_value(self.canonical_body()):
            raise CaseReplayV2Error("case replay bundle content-address mismatch")
        return verification


def verify_case_replay_bundle(value: Mapping[str, object]) -> CaseReplayVerificationV2:
    """Rebuild projections from bundle bytes without database or provider access."""

    raw = _copy_mapping(value, field_name="case replay bundle")
    _require_exact_keys(raw, expected=_BUNDLE_KEYS, field_name="case replay bundle")
    if raw.get("schema") != CASE_REPLAY_BUNDLE_SCHEMA_V2:
        raise CaseReplayV2Error(f"unsupported replay bundle schema: {raw.get('schema')}")
    required_mappings = {
        name: raw.get(name)
        for name in (
            "manifest",
            "ledger_bundle",
            "runtime_identity",
            "migration_registry",
            "epistemic_policy",
            "trust_policy",
        )
    }
    if any(not isinstance(item, Mapping) for item in required_mappings.values()):
        raise CaseReplayV2Error("case replay bundle contains malformed object fields")

    manifest = CaseReplayManifestV2.from_dict(
        cast(Mapping[str, object], required_mappings["manifest"])
    )
    ledger = CaseLedgerBundle.from_dict(
        cast(Mapping[str, object], required_mappings["ledger_bundle"])
    )
    runtime = _runtime_from_snapshot(
        cast(Mapping[str, object], required_mappings["runtime_identity"])
    )
    registry_snapshot = _validate_registry_snapshot(
        cast(Mapping[str, object], required_mappings["migration_registry"])
    )
    epistemic_policy = _parse_epistemic_policy(
        cast(Mapping[str, object], required_mappings["epistemic_policy"])
    )
    trust_policy = _parse_trust_policy(
        cast(Mapping[str, object], required_mappings["trust_policy"])
    )

    epistemic = EpistemicProjectionV2.build(
        case_id=ledger.case_id,
        events=ledger.events,
        policy=epistemic_policy,
    )
    trust = EvidenceTrustGraph.build(
        case_id=ledger.case_id,
        events=ledger.events,
        epistemic_projection=epistemic,
        policy=trust_policy,
    )

    checks = {
        "case_id": manifest.case_id == ledger.case_id,
        "ledger_head": manifest.ledger_head == ledger.head_event_id,
        "ledger_bundle_digest": manifest.ledger_bundle_digest == ledger.bundle_digest,
        "epistemic_projection_identity": (
            manifest.epistemic_projection_identity == epistemic.projection_identity
        ),
        "trust_graph_identity": manifest.trust_graph_identity == trust.graph_identity,
        "epistemic_policy_identity": (
            manifest.epistemic_policy_identity == epistemic_policy.policy_identity
        ),
        "trust_policy_identity": manifest.trust_policy_identity == trust_policy.policy_identity,
        "runtime_identity_digest": (
            manifest.runtime_identity_digest
            == ContentAddress.for_value(runtime.canonical_dict())
        ),
        "migration_registry_digest": (
            manifest.migration_registry_digest == ContentAddress.for_value(registry_snapshot)
        ),
        "case_schema_version": manifest.case_schema_version == runtime.schema_version,
        "evidence_digests": manifest.evidence_digests == tuple(runtime.evidence_digests),
    }
    failed = tuple(sorted(name for name, passed in checks.items() if not passed))
    if failed:
        raise CaseReplayV2Error("case replay identity mismatch: " + ", ".join(failed))

    expected_schema_identities = tuple(
        sorted(
            {
                LEDGER_BUNDLE_SCHEMA_V1,
                LEDGER_EVENT_SCHEMA_V1,
                ASSERTION_SCHEMA_V2,
                EPISTEMIC_POLICY_SCHEMA_V2,
                EPISTEMIC_PROJECTION_SCHEMA_V2,
                TRUST_POLICY_SCHEMA_V1,
                TRUST_GRAPH_SCHEMA_V1,
                runtime.identity_schema,
                runtime.schema_version,
            }
        )
    )
    if manifest.schema_identities != expected_schema_identities:
        raise CaseReplayV2Error("case replay schema identity set mismatch")

    raw_bundle_identity = _address(raw.get("bundle_identity"), field_name="bundle_identity")
    body_without_identity = dict(raw)
    body_without_identity.pop("bundle_identity", None)
    if raw_bundle_identity != ContentAddress.for_value(body_without_identity):
        raise CaseReplayV2Error("case replay bundle content-address mismatch")

    return CaseReplayVerificationV2(
        manifest_identity=manifest.manifest_identity,
        ledger_head=ledger.head_event_id,
        epistemic_projection_identity=epistemic.projection_identity,
        trust_graph_identity=trust.graph_identity,
        runtime_identity_digest=ContentAddress.for_value(runtime.canonical_dict()),
    )


@dataclass(frozen=True, slots=True)
class CaseReplayComparisonV2:
    relation: ReplayRelation
    baseline_manifest_identity: ContentAddress
    candidate_manifest_identity: ContentAddress
    differing_fields: tuple[str, ...]
    migration_path: tuple[str, ...] = ()
    schema: str = CASE_REPLAY_COMPARISON_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != CASE_REPLAY_COMPARISON_SCHEMA_V2:
            raise CaseReplayV2Error("unsupported replay comparison schema")
        if self.relation is ReplayRelation.IDENTICAL and (
            self.differing_fields or self.migration_path
        ):
            raise CaseReplayV2Error("IDENTICAL replay cannot contain differences")
        if (
            self.relation is ReplayRelation.CROSS_VERSION_COMPARABLE
            and len(self.migration_path) < 2
        ):
            raise CaseReplayV2Error("cross-version comparison requires migration path")


def compare_case_replay_manifests(
    baseline: CaseReplayManifestV2,
    candidate: CaseReplayManifestV2,
    *,
    migration_registry: CaseMigrationRegistry,
) -> CaseReplayComparisonV2:
    """Classify exact manifest identity; cross-version needs an explicit registry path."""

    baseline.verify()
    candidate.verify()
    if baseline.manifest_identity == candidate.manifest_identity:
        return CaseReplayComparisonV2(
            relation=ReplayRelation.IDENTICAL,
            baseline_manifest_identity=baseline.manifest_identity,
            candidate_manifest_identity=candidate.manifest_identity,
            differing_fields=(),
        )

    fields = (
        "case_id",
        "ledger_head",
        "ledger_bundle_digest",
        "epistemic_projection_identity",
        "trust_graph_identity",
        "epistemic_policy_identity",
        "trust_policy_identity",
        "runtime_identity_digest",
        "migration_registry_digest",
        "case_schema_version",
        "schema_identities",
        "evidence_digests",
    )
    differing = tuple(
        field
        for field in fields
        if getattr(baseline, field) != getattr(candidate, field)
    )
    if baseline.case_id != candidate.case_id:
        return CaseReplayComparisonV2(
            relation=ReplayRelation.DIFFERENT,
            baseline_manifest_identity=baseline.manifest_identity,
            candidate_manifest_identity=candidate.manifest_identity,
            differing_fields=differing,
        )

    if baseline.case_schema_version != candidate.case_schema_version:
        if candidate.migration_registry_digest != ContentAddress.for_value(
            migration_registry.canonical_dict()
        ):
            raise CaseReplayV2Error(
                "candidate replay is not bound to supplied migration registry"
            )
        try:
            path = migration_registry.path(
                baseline.case_schema_version,
                candidate.case_schema_version,
            )
        except ValueError as exc:
            raise CaseReplayV2Error(str(exc)) from exc
        return CaseReplayComparisonV2(
            relation=ReplayRelation.CROSS_VERSION_COMPARABLE,
            baseline_manifest_identity=baseline.manifest_identity,
            candidate_manifest_identity=candidate.manifest_identity,
            differing_fields=differing,
            migration_path=path,
        )

    return CaseReplayComparisonV2(
        relation=ReplayRelation.DIFFERENT,
        baseline_manifest_identity=baseline.manifest_identity,
        candidate_manifest_identity=candidate.manifest_identity,
        differing_fields=differing,
    )