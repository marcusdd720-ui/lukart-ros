"""FIV-02 bounded verification of trust-critical state invariants.

This module is verification-only. It exercises existing production contracts using
synthetic, isolated state and emits deterministic content-addressed traces. It does
not write real case data, create a second Product authority, or claim whole-system
formal verification.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from core.case_ledger import CanonicalCaseLedger
from core.case_ledger.contracts import (
    CaseId,
    CaseLedgerContractError,
    ContentAddress,
    ObjectId,
    ObjectRevision,
)
from core.case_replay_v2 import CaseReplayBundleV2, verify_case_replay_bundle
from core.enterprise.authorization import AuthorizationEngine, ResourceDescriptor, RoleDefinition
from core.enterprise.contracts import DataClassification, Permission
from core.p3.contracts import P3ContractError, RuntimeIdentity, canonical_json
from core.p3.versioning import CaseMigrationRegistry, MigrationStep, VersionedCase
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicLedgerService, EpistemicPolicyV2
from knowledge.evidence_trust_graph import TrustPolicyV1

FIV02_REGISTRY_SCHEMA = "lukart.fiv02-invariant-registry.v2"
FIV02_TRACE_SCHEMA = "lukart.fiv02-invariant-trace.v2"
FIV02_RESULT_SCHEMA = "lukart.fiv02-invariant-result.v2"
FIV02_REPORT_SCHEMA = "lukart.fiv02-verification-report.v2"
FIV02_MAX_TRACE_STEPS = 64


class FIV02VerificationError(ValueError):
    """Fail-closed FIV-02 verification contract violation."""


class FIV02InvariantId(StrEnum):
    APPEND_ONLY_EXACT_HEAD = "APPEND_ONLY_EXACT_HEAD"
    CONTENT_IDENTITY_DOMAIN_SEPARATION = "CONTENT_IDENTITY_DOMAIN_SEPARATION"
    MIGRATION_PATH_DETERMINISM = "MIGRATION_PATH_DETERMINISM"
    AUTHORIZATION_ISOLATION = "AUTHORIZATION_ISOLATION"
    REPLAY_PROJECTION_EQUIVALENCE = "REPLAY_PROJECTION_EQUIVALENCE"
    RECOVERY_ATOMICITY = "RECOVERY_ATOMICITY"


@dataclass(frozen=True, slots=True)
class FIV02InvariantDefinition:
    invariant_id: FIV02InvariantId
    subsystem: str
    statement: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "invariant_id": self.invariant_id.value,
            "subsystem": self.subsystem,
            "statement": self.statement,
        }


def _definitions() -> tuple[FIV02InvariantDefinition, ...]:
    values = (
        FIV02InvariantDefinition(
            FIV02InvariantId.APPEND_ONLY_EXACT_HEAD,
            "canonical-case-ledger",
            "Only the exact current head may advance one synthetic case history.",
        ),
        FIV02InvariantDefinition(
            FIV02InvariantId.CONTENT_IDENTITY_DOMAIN_SEPARATION,
            "canonical-object-identity",
            "Immutable identities are deterministic and bind object identity plus content.",
        ),
        FIV02InvariantDefinition(
            FIV02InvariantId.MIGRATION_PATH_DETERMINISM,
            "case-migrations",
            "Explicit migrations are deterministic and ambiguous or unstable paths fail closed.",
        ),
        FIV02InvariantDefinition(
            FIV02InvariantId.AUTHORIZATION_ISOLATION,
            "enterprise-authorization",
            "Tenant, case, permission and classification boundaries deny unauthorized access.",
        ),
        FIV02InvariantDefinition(
            FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE,
            "case-replay-v2",
            "Replay rebuild reproduces exact manifest-bound projection identities.",
        ),
        FIV02InvariantDefinition(
            FIV02InvariantId.RECOVERY_ATOMICITY,
            "canonical-ledger-recovery",
            "Injected mid-restore failure leaves no partial case history and recovery remains exact.",
        ),
    )
    return tuple(sorted(values, key=lambda item: item.invariant_id.value))


@dataclass(frozen=True, slots=True)
class FIV02Registry:
    definitions: tuple[FIV02InvariantDefinition, ...]
    registry_identity: ContentAddress
    schema: str = FIV02_REGISTRY_SCHEMA

    @classmethod
    def reference(cls) -> "FIV02Registry":
        definitions = _definitions()
        body = {
            "schema": FIV02_REGISTRY_SCHEMA,
            "authority": "verification-only",
            "failure_semantics": "fail-closed-no-partial-pass",
            "max_trace_steps": FIV02_MAX_TRACE_STEPS,
            "definitions": [item.canonical_dict() for item in definitions],
        }
        return cls(definitions=definitions, registry_identity=ContentAddress.for_value(body))

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority": "verification-only",
            "failure_semantics": "fail-closed-no-partial-pass",
            "max_trace_steps": FIV02_MAX_TRACE_STEPS,
            "definitions": [item.canonical_dict() for item in self.definitions],
        }

    def verify(self) -> None:
        if self.schema != FIV02_REGISTRY_SCHEMA:
            raise FIV02VerificationError(f"unsupported FIV-02 registry schema: {self.schema}")
        if self.definitions != _definitions():
            raise FIV02VerificationError("FIV-02 registry does not match the fixed reference set")
        if self.registry_identity != ContentAddress.for_value(self.canonical_body()):
            raise FIV02VerificationError("FIV-02 registry content-address mismatch")


@dataclass(frozen=True, slots=True)
class FIV02TracePoint:
    index: int
    action: str
    outcome: str
    state_identity: ContentAddress
    point_identity: ContentAddress

    @classmethod
    def build(
        cls,
        *,
        index: int,
        action: str,
        outcome: str,
        state: Mapping[str, object],
    ) -> "FIV02TracePoint":
        if index < 0:
            raise FIV02VerificationError("trace index cannot be negative")
        action = action.strip()
        outcome = outcome.strip()
        if not action or not outcome:
            raise FIV02VerificationError("trace action/outcome cannot be blank")
        state_identity = ContentAddress.for_value(dict(state))
        body = {
            "schema": "lukart.fiv02-trace-point.v2",
            "index": index,
            "action": action,
            "outcome": outcome,
            "state_identity": state_identity.canonical_dict(),
        }
        return cls(
            index=index,
            action=action,
            outcome=outcome,
            state_identity=state_identity,
            point_identity=ContentAddress.for_value(body),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "lukart.fiv02-trace-point.v2",
            "index": self.index,
            "action": self.action,
            "outcome": self.outcome,
            "state_identity": self.state_identity.canonical_dict(),
            "point_identity": self.point_identity.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class FIV02InvariantTrace:
    invariant_id: FIV02InvariantId
    points: tuple[FIV02TracePoint, ...]
    trace_identity: ContentAddress
    schema: str = FIV02_TRACE_SCHEMA

    @classmethod
    def build(
        cls,
        *,
        invariant_id: FIV02InvariantId,
        points: tuple[FIV02TracePoint, ...],
    ) -> "FIV02InvariantTrace":
        if not points:
            raise FIV02VerificationError("FIV-02 trace cannot be empty")
        if len(points) > FIV02_MAX_TRACE_STEPS:
            raise FIV02VerificationError("FIV-02 trace step budget exceeded")
        if tuple(point.index for point in points) != tuple(range(len(points))):
            raise FIV02VerificationError("FIV-02 trace indexes must be contiguous")
        body = {
            "schema": FIV02_TRACE_SCHEMA,
            "invariant_id": invariant_id.value,
            "points": [point.canonical_dict() for point in points],
        }
        return cls(
            invariant_id=invariant_id,
            points=points,
            trace_identity=ContentAddress.for_value(body),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "invariant_id": self.invariant_id.value,
            "points": [point.canonical_dict() for point in self.points],
        }

    def verify(self) -> None:
        if self.schema != FIV02_TRACE_SCHEMA:
            raise FIV02VerificationError("unsupported FIV-02 trace schema")
        if not self.points or len(self.points) > FIV02_MAX_TRACE_STEPS:
            raise FIV02VerificationError("FIV-02 trace violates step bounds")
        if tuple(point.index for point in self.points) != tuple(range(len(self.points))):
            raise FIV02VerificationError("FIV-02 trace indexes are invalid")
        if self.trace_identity != ContentAddress.for_value(self.canonical_body()):
            raise FIV02VerificationError("FIV-02 trace content-address mismatch")


class _TraceBuilder:
    def __init__(self, invariant_id: FIV02InvariantId) -> None:
        self.invariant_id = invariant_id
        self._points: list[FIV02TracePoint] = []

    def add(self, action: str, outcome: str, state: Mapping[str, object]) -> None:
        if len(self._points) >= FIV02_MAX_TRACE_STEPS:
            raise FIV02VerificationError("FIV-02 trace step budget exceeded")
        self._points.append(
            FIV02TracePoint.build(
                index=len(self._points),
                action=action,
                outcome=outcome,
                state=state,
            )
        )

    def finish(self) -> FIV02InvariantTrace:
        return FIV02InvariantTrace.build(
            invariant_id=self.invariant_id,
            points=tuple(self._points),
        )


@dataclass(frozen=True, slots=True)
class FIV02InvariantResult:
    invariant_id: FIV02InvariantId
    trace: FIV02InvariantTrace
    evidence_identity: ContentAddress
    result_identity: ContentAddress
    schema: str = FIV02_RESULT_SCHEMA
    outcome: str = "PASS"

    @classmethod
    def build(
        cls,
        *,
        invariant_id: FIV02InvariantId,
        trace: FIV02InvariantTrace,
        evidence: Mapping[str, object],
    ) -> "FIV02InvariantResult":
        trace.verify()
        evidence_identity = ContentAddress.for_value(
            {
                "schema": "lukart.fiv02-evidence.v2",
                "invariant_id": invariant_id.value,
                "evidence": dict(evidence),
            }
        )
        body = {
            "schema": FIV02_RESULT_SCHEMA,
            "invariant_id": invariant_id.value,
            "outcome": "PASS",
            "trace_identity": trace.trace_identity.canonical_dict(),
            "evidence_identity": evidence_identity.canonical_dict(),
        }
        return cls(
            invariant_id=invariant_id,
            trace=trace,
            evidence_identity=evidence_identity,
            result_identity=ContentAddress.for_value(body),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "invariant_id": self.invariant_id.value,
            "outcome": self.outcome,
            "trace_identity": self.trace.trace_identity.canonical_dict(),
            "evidence_identity": self.evidence_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.schema != FIV02_RESULT_SCHEMA or self.outcome != "PASS":
            raise FIV02VerificationError("invalid FIV-02 result contract")
        if self.trace.invariant_id is not self.invariant_id:
            raise FIV02VerificationError("FIV-02 result/trace invariant mismatch")
        self.trace.verify()
        if self.result_identity != ContentAddress.for_value(self.canonical_body()):
            raise FIV02VerificationError("FIV-02 result content-address mismatch")


@dataclass(frozen=True, slots=True)
class FIV02VerificationReport:
    code_sha: str
    registry_identity: ContentAddress
    results: tuple[FIV02InvariantResult, ...]
    report_identity: ContentAddress
    schema: str = FIV02_REPORT_SCHEMA
    outcome: str = "PASS"

    @classmethod
    def build(
        cls,
        *,
        code_sha: str,
        registry: FIV02Registry,
        results: tuple[FIV02InvariantResult, ...],
    ) -> "FIV02VerificationReport":
        registry.verify()
        expected_ids = tuple(item.invariant_id for item in registry.definitions)
        if tuple(result.invariant_id for result in results) != expected_ids:
            raise FIV02VerificationError("FIV-02 report is missing, duplicated or reorders checks")
        for result in results:
            result.verify()
        body = {
            "schema": FIV02_REPORT_SCHEMA,
            "code_sha": code_sha,
            "registry_identity": registry.registry_identity.canonical_dict(),
            "outcome": "PASS",
            "results": [
                {
                    "invariant_id": result.invariant_id.value,
                    "result_identity": result.result_identity.canonical_dict(),
                }
                for result in results
            ],
        }
        return cls(
            code_sha=code_sha,
            registry_identity=registry.registry_identity,
            results=results,
            report_identity=ContentAddress.for_value(body),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "code_sha": self.code_sha,
            "registry_identity": self.registry_identity.canonical_dict(),
            "outcome": self.outcome,
            "results": [
                {
                    "invariant_id": result.invariant_id.value,
                    "result_identity": result.result_identity.canonical_dict(),
                }
                for result in self.results
            ],
        }

    def verify(self) -> None:
        if self.schema != FIV02_REPORT_SCHEMA or self.outcome != "PASS":
            raise FIV02VerificationError("invalid FIV-02 report contract")
        registry = FIV02Registry.reference()
        registry.verify()
        if self.registry_identity != registry.registry_identity:
            raise FIV02VerificationError("FIV-02 report registry identity mismatch")
        expected_ids = tuple(item.invariant_id for item in registry.definitions)
        if tuple(result.invariant_id for result in self.results) != expected_ids:
            raise FIV02VerificationError("FIV-02 report invariant set mismatch")
        for result in self.results:
            result.verify()
        if self.report_identity != ContentAddress.for_value(self.canonical_body()):
            raise FIV02VerificationError("FIV-02 report content-address mismatch")


def _git_object_id(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if normalized != value or len(normalized) not in (40, 64):
        raise FIV02VerificationError(f"{field_name} must be canonical 40- or 64-hex Git identity")
    if normalized.lower() != normalized:
        raise FIV02VerificationError(f"{field_name} must be lowercase hex")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise FIV02VerificationError(f"{field_name} must be lowercase hex") from exc
    return normalized


def _runtime(code_sha: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code_sha,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("fiv02-synthetic@1",),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=("e" * 64,),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest="f" * 64,
        python_implementation="CPython",
        python_version="3.11",
        platform_tag="synthetic-portable",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _serialized(value: object) -> dict[str, object]:
    canonical = value.canonical_dict()  # type: ignore[attr-defined]
    decoded = json.loads(canonical_json(canonical))
    if not isinstance(decoded, dict):
        raise FIV02VerificationError("synthetic fixture did not serialize to an object")
    return cast(dict[str, object], decoded)


def _append_only_probe(root: Path, code_sha: str) -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.APPEND_ONLY_EXACT_HEAD
    trace = _TraceBuilder(invariant_id)
    runtime = _runtime(code_sha)
    case_id = CaseId("CASE-FIV02-HEAD")
    with CanonicalCaseLedger(root / "append-only.db") as ledger:
        first = ledger.append_event(
            case_id=case_id,
            event_type="fiv02.synthetic.v1",
            runtime_identity=runtime,
            payload={"step": 1},
            expected_head=None,
        )
        trace.add(
            "append-genesis",
            "accepted",
            {"event_count": 1, "head": first.event_id.canonical_dict()},
        )
        stale_rejected = False
        try:
            ledger.append_event(
                case_id=case_id,
                event_type="fiv02.synthetic.v1",
                runtime_identity=runtime,
                payload={"step": "stale"},
                expected_head=None,
            )
        except CaseLedgerContractError:
            stale_rejected = True
        if not stale_rejected:
            raise FIV02VerificationError("APPEND_ONLY_EXACT_HEAD accepted stale head")
        trace.add(
            "append-stale-head",
            "rejected",
            {"event_count": 1, "head": first.event_id.canonical_dict()},
        )
        second = ledger.append_event(
            case_id=case_id,
            event_type="fiv02.synthetic.v1",
            runtime_identity=runtime,
            payload={"step": 2},
            expected_head=first.event_id,
        )
        events = ledger.events(case_id)
        if (
            len(events) != 2
            or events[0].event_id != first.event_id
            or events[1].previous_event_id != first.event_id
            or events[1].event_id != second.event_id
        ):
            raise FIV02VerificationError("APPEND_ONLY_EXACT_HEAD chain changed unexpectedly")
        trace.add(
            "append-exact-head",
            "accepted",
            {"event_count": 2, "head": second.event_id.canonical_dict()},
        )
    built = trace.finish()
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=built,
        evidence={
            "stale_head_rejected": stale_rejected,
            "final_event_count": 2,
            "final_head": second.event_id.canonical_dict(),
        },
    )


def _identity_probe() -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.CONTENT_IDENTITY_DOMAIN_SEPARATION
    trace = _TraceBuilder(invariant_id)
    object_a = ObjectId("OBJ-FIV02-A")
    object_b = ObjectId("OBJ-FIV02-B")
    first = ObjectRevision.build(
        object_id=object_a,
        schema_version="object.v1",
        content={"value": 1},
    )
    same = ObjectRevision.build(
        object_id=object_a,
        schema_version="object.v1",
        content={"value": 1},
    )
    changed_content = ObjectRevision.build(
        object_id=object_a,
        schema_version="object.v1",
        content={"value": 2},
    )
    changed_object = ObjectRevision.build(
        object_id=object_b,
        schema_version="object.v1",
        content={"value": 1},
    )
    if first.revision_id != same.revision_id:
        raise FIV02VerificationError("CONTENT_IDENTITY_DOMAIN_SEPARATION is nondeterministic")
    if first.revision_id in {changed_content.revision_id, changed_object.revision_id}:
        raise FIV02VerificationError("CONTENT_IDENTITY_DOMAIN_SEPARATION lost domain binding")
    trace.add(
        "same-object-same-content",
        "stable",
        {"revision_id": first.revision_id.canonical_dict()},
    )
    trace.add(
        "same-object-changed-content",
        "separated",
        {"revision_id": changed_content.revision_id.canonical_dict()},
    )
    trace.add(
        "changed-object-same-content",
        "separated",
        {"revision_id": changed_object.revision_id.canonical_dict()},
    )
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=trace.finish(),
        evidence={
            "stable_identity": first.revision_id == same.revision_id,
            "content_domain_separated": first.revision_id != changed_content.revision_id,
            "object_domain_separated": first.revision_id != changed_object.revision_id,
        },
    )


def _migration_probe() -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.MIGRATION_PATH_DETERMINISM
    trace = _TraceBuilder(invariant_id)
    source = VersionedCase.build(
        case_id="CASE-FIV02-MIGRATION",
        schema_version="case.v1",
        payload={"value": 1},
    )
    stable = CaseMigrationRegistry()
    stable.register(
        MigrationStep(
            "case.v1",
            "case.v2",
            lambda payload: {**payload, "schema_upgraded": True},
        )
    )
    first = stable.migrate(source, "case.v2")
    second = stable.migrate(source, "case.v2")
    if first.target.payload_digest != second.target.payload_digest or first.path_digest != second.path_digest:
        raise FIV02VerificationError("MIGRATION_PATH_DETERMINISM produced different targets")
    trace.add(
        "repeat-explicit-migration",
        "stable",
        {
            "target_digest": first.target.payload_digest,
            "path_digest": first.path_digest,
        },
    )

    ambiguous = CaseMigrationRegistry()
    ambiguous.register(MigrationStep("case.v1", "case.v3", lambda payload: dict(payload)))
    ambiguous.register(MigrationStep("case.v1", "case.v2", lambda payload: dict(payload)))
    ambiguous.register(MigrationStep("case.v2", "case.v3", lambda payload: dict(payload)))
    ambiguous_rejected = False
    try:
        ambiguous.path("case.v1", "case.v3")
    except P3ContractError:
        ambiguous_rejected = True
    if not ambiguous_rejected:
        raise FIV02VerificationError("MIGRATION_PATH_DETERMINISM accepted ambiguous route")
    trace.add(
        "ambiguous-route",
        "rejected",
        {"source": "case.v1", "target": "case.v3"},
    )

    counter = 0

    def unstable(payload: Mapping[str, object]) -> Mapping[str, object]:
        nonlocal counter
        counter += 1
        return {**payload, "counter": counter}

    unstable_registry = CaseMigrationRegistry()
    unstable_registry.register(MigrationStep("case.v1", "case.v2", unstable))
    nondeterministic_rejected = False
    try:
        unstable_registry.migrate(source, "case.v2")
    except P3ContractError:
        nondeterministic_rejected = True
    if not nondeterministic_rejected:
        raise FIV02VerificationError("MIGRATION_PATH_DETERMINISM accepted unstable migration")
    trace.add(
        "unstable-migration",
        "rejected",
        {"source_digest": source.payload_digest},
    )
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=trace.finish(),
        evidence={
            "target_digest": first.target.payload_digest,
            "path_digest": first.path_digest,
            "ambiguous_rejected": ambiguous_rejected,
            "nondeterministic_rejected": nondeterministic_rejected,
        },
    )


def _authorization_probe() -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.AUTHORIZATION_ISOLATION
    trace = _TraceBuilder(invariant_id)
    engine = AuthorizationEngine(
        (
            RoleDefinition(
                role="reader",
                permissions=(Permission.CASE_READ,),
                max_classification=DataClassification.CONFIDENTIAL,
            ),
        )
    )
    context = engine.build_context(
        subject_id="subject-fiv02",
        tenant_id="TENANT-A",
        roles=("reader",),
        case_ids=("CASE-A",),
    )
    own = ResourceDescriptor(
        resource_id="res-own",
        tenant_id="TENANT-A",
        case_id="CASE-A",
        classification=DataClassification.CONFIDENTIAL,
    )
    scenarios = (
        ("own-case-read", Permission.CASE_READ, own, True),
        (
            "other-case-read",
            Permission.CASE_READ,
            ResourceDescriptor(
                resource_id="res-other-case",
                tenant_id="TENANT-A",
                case_id="CASE-B",
                classification=DataClassification.INTERNAL,
            ),
            False,
        ),
        (
            "cross-tenant-read",
            Permission.CASE_READ,
            ResourceDescriptor(
                resource_id="res-other-tenant",
                tenant_id="TENANT-B",
                case_id="CASE-A",
                classification=DataClassification.INTERNAL,
            ),
            False,
        ),
        (
            "classification-over-clearance",
            Permission.CASE_READ,
            ResourceDescriptor(
                resource_id="res-restricted",
                tenant_id="TENANT-A",
                case_id="CASE-A",
                classification=DataClassification.RESTRICTED,
            ),
            False,
        ),
        ("undeclared-write", Permission.CASE_WRITE, own, False),
    )
    decision_digests: list[str] = []
    for name, permission, resource, expected in scenarios:
        decision = engine.decide(context, permission, resource, strict_scope=True)
        repeated = engine.decide(context, permission, resource, strict_scope=True)
        if decision.allowed is not expected:
            raise FIV02VerificationError(f"AUTHORIZATION_ISOLATION violated scenario: {name}")
        if decision.digest() != repeated.digest():
            raise FIV02VerificationError(f"AUTHORIZATION_ISOLATION is nondeterministic: {name}")
        decision_digests.append(decision.digest())
        trace.add(
            name,
            "allowed" if decision.allowed else "denied",
            {
                "decision_digest": decision.digest(),
                "reason": decision.reason,
            },
        )
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=trace.finish(),
        evidence={
            "scenario_count": len(scenarios),
            "decision_digests": decision_digests,
            "only_expected_access_allowed": True,
        },
    )


def _replay_probe(root: Path, code_sha: str) -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE
    trace = _TraceBuilder(invariant_id)
    runtime = _runtime(code_sha)
    case_id = CaseId("CASE-FIV02-REPLAY")
    epistemic_policy = EpistemicPolicyV2.reference()
    with CanonicalCaseLedger(root / "replay.db") as ledger:
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-FIV02-REPLAY"),
            assertion_type="claim.v1",
            content={"value": "synthetic"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=runtime,
            expected_head=None,
        )
        ledger_bundle = ledger.export_case(case_id)
    replay = CaseReplayBundleV2.build(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime,
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=epistemic_policy,
        trust_policy=TrustPolicyV1.reference(),
    )
    serialized = _serialized(replay)
    first = verify_case_replay_bundle(serialized)
    second = verify_case_replay_bundle(serialized)
    if first != second:
        raise FIV02VerificationError("REPLAY_PROJECTION_EQUIVALENCE rebuild is nondeterministic")
    if (
        first.manifest_identity != replay.manifest.manifest_identity
        or first.epistemic_projection_identity != replay.manifest.epistemic_projection_identity
        or first.trust_graph_identity != replay.manifest.trust_graph_identity
    ):
        raise FIV02VerificationError("REPLAY_PROJECTION_EQUIVALENCE identity mismatch")
    trace.add(
        "build-synthetic-replay",
        "built",
        {
            "manifest_identity": replay.manifest.manifest_identity.canonical_dict(),
            "ledger_head": replay.manifest.ledger_head.canonical_dict()
            if replay.manifest.ledger_head
            else None,
        },
    )
    trace.add(
        "offline-rebuild-1",
        "equivalent",
        {
            "epistemic_projection_identity": first.epistemic_projection_identity.canonical_dict(),
            "trust_graph_identity": first.trust_graph_identity.canonical_dict(),
        },
    )
    trace.add(
        "offline-rebuild-2",
        "equivalent",
        {
            "epistemic_projection_identity": second.epistemic_projection_identity.canonical_dict(),
            "trust_graph_identity": second.trust_graph_identity.canonical_dict(),
        },
    )
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=trace.finish(),
        evidence={
            "manifest_identity": first.manifest_identity.canonical_dict(),
            "epistemic_projection_identity": first.epistemic_projection_identity.canonical_dict(),
            "trust_graph_identity": first.trust_graph_identity.canonical_dict(),
            "repeat_rebuild_equal": first == second,
        },
    )


def _recovery_probe(root: Path, code_sha: str) -> FIV02InvariantResult:
    invariant_id = FIV02InvariantId.RECOVERY_ATOMICITY
    trace = _TraceBuilder(invariant_id)
    runtime = _runtime(code_sha)
    case_id = CaseId("CASE-FIV02-RECOVERY")
    with CanonicalCaseLedger(root / "recovery-source.db") as source:
        first = source.append_event(
            case_id=case_id,
            event_type="fiv02.synthetic.v1",
            runtime_identity=runtime,
            payload={"step": 1},
            expected_head=None,
        )
        source.append_event(
            case_id=case_id,
            event_type="fiv02.synthetic.v1",
            runtime_identity=runtime,
            payload={"step": 2},
            expected_head=first.event_id,
        )
        bundle = source.export_case(case_id)

    target_path = root / "recovery-target.db"
    serialized = _serialized(bundle)
    with CanonicalCaseLedger(target_path) as target:
        raw = sqlite3.connect(target_path)
        try:
            raw.execute(
                """
                CREATE TRIGGER fiv02_fail_second
                BEFORE INSERT ON provenance
                WHEN NEW.payload_json LIKE '%"case_sequence":1%'
                BEGIN
                    SELECT RAISE(ABORT, 'fiv02 injected failure');
                END
                """
            )
            raw.commit()
        finally:
            raw.close()

        injected_failure_rejected = False
        try:
            target.restore_case(case_id, serialized)
        except CaseLedgerContractError:
            injected_failure_rejected = True
        if not injected_failure_rejected:
            raise FIV02VerificationError("RECOVERY_ATOMICITY accepted injected partial restore")
        if target.events(case_id) != ():
            raise FIV02VerificationError("RECOVERY_ATOMICITY left partial canonical history")
        trace.add(
            "restore-with-injected-second-write-failure",
            "rolled-back",
            {"event_count": 0, "head": None},
        )

        raw = sqlite3.connect(target_path)
        try:
            raw.execute("DROP TRIGGER fiv02_fail_second")
            raw.commit()
        finally:
            raw.close()

        restored = target.restore_case(case_id, serialized)
        if restored != bundle or target.export_case(case_id) != bundle:
            raise FIV02VerificationError("RECOVERY_ATOMICITY exact retry recovery mismatch")
        trace.add(
            "retry-exact-restore",
            "accepted",
            {
                "event_count": len(restored.events),
                "head": restored.head_event_id.canonical_dict()
                if restored.head_event_id
                else None,
                "bundle_digest": restored.bundle_digest.canonical_dict(),
            },
        )
    return FIV02InvariantResult.build(
        invariant_id=invariant_id,
        trace=trace.finish(),
        evidence={
            "injected_failure_rejected": injected_failure_rejected,
            "partial_event_count_after_failure": 0,
            "restored_bundle_digest": bundle.bundle_digest.canonical_dict(),
        },
    )


def verify_fiv02(
    *,
    code_sha: str,
    expected_code_sha: str,
    workspace: Path,
) -> FIV02VerificationReport:
    """Run the fixed FIV-02 synthetic bounded invariant suite.

    The caller controls only exact SHA binding and the scratch workspace. The invariant
    set and trace budget are fixed by the versioned registry and cannot be caller-reduced.
    """

    code_sha = _git_object_id(code_sha, field_name="code_sha")
    expected_code_sha = _git_object_id(expected_code_sha, field_name="expected_code_sha")
    if code_sha != expected_code_sha:
        raise FIV02VerificationError("code_sha does not match expected_code_sha")

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    registry = FIV02Registry.reference()
    registry.verify()

    try:
        with tempfile.TemporaryDirectory(prefix="fiv02-", dir=workspace) as directory:
            root = Path(directory)
            by_id = {
                FIV02InvariantId.APPEND_ONLY_EXACT_HEAD: _append_only_probe(root, code_sha),
                FIV02InvariantId.CONTENT_IDENTITY_DOMAIN_SEPARATION: _identity_probe(),
                FIV02InvariantId.MIGRATION_PATH_DETERMINISM: _migration_probe(),
                FIV02InvariantId.AUTHORIZATION_ISOLATION: _authorization_probe(),
                FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE: _replay_probe(root, code_sha),
                FIV02InvariantId.RECOVERY_ATOMICITY: _recovery_probe(root, code_sha),
            }
    except FIV02VerificationError:
        raise
    except Exception as exc:
        raise FIV02VerificationError(
            f"FIV-02 production-contract probe failed closed: {type(exc).__name__}: {exc}"
        ) from exc

    ordered_results = tuple(by_id[item.invariant_id] for item in registry.definitions)
    report = FIV02VerificationReport.build(
        code_sha=code_sha,
        registry=registry,
        results=ordered_results,
    )
    report.verify()
    return report
