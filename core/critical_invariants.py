"""IV-01 bounded verification of trust-critical LUKART ROS invariants.

The verifier is deliberately a read-only orchestration layer. It delegates semantic
checks to the existing Canonical Case Ledger, Case Replay v2, migration, Epistemic v2
and Semantic Change v2 production contracts instead of creating a parallel truth
authority or reimplementing those contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.case_ledger import CanonicalCaseLedger
from core.case_ledger.contracts import CaseId, ContentAddress, LedgerEvent
from core.case_replay_v2 import verify_case_replay_bundle
from core.p3.versioning import CaseMigrationRegistry, VersionedCase
from core.semantic_change_v2 import (
    ImmutableArtifactRef,
    SemanticChangeGraphV2,
    SemanticPropagationPolicyV2,
)
from knowledge.epistemic_assertions import EpistemicPolicyV2, EpistemicProjectionV2

CRITICAL_INVARIANT_REGISTRY_SCHEMA_V1 = "lukart.critical-invariant-registry.v1"
CRITICAL_INVARIANT_RESULT_SCHEMA_V1 = "lukart.critical-invariant-result.v1"
CRITICAL_INVARIANT_REPORT_SCHEMA_V1 = "lukart.critical-invariant-report.v1"


class CriticalInvariantVerificationError(ValueError):
    """Fail-closed IV-01 verification contract violation."""


class CriticalInvariantId(StrEnum):
    CCL_BUNDLE_INTEGRITY = "CCL_BUNDLE_INTEGRITY"
    RECOVERY_IDENTITY_EQUIVALENCE = "RECOVERY_IDENTITY_EQUIVALENCE"
    REPLAY_REBUILD_EQUIVALENCE = "REPLAY_REBUILD_EQUIVALENCE"
    MIGRATION_DETERMINISM = "MIGRATION_DETERMINISM"
    EPISTEMIC_REBUILD_EQUIVALENCE = "EPISTEMIC_REBUILD_EQUIVALENCE"
    SEMANTIC_PROPAGATION_BOUNDED = "SEMANTIC_PROPAGATION_BOUNDED"


class VerificationOutcome(StrEnum):
    PASS = "PASS"


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CriticalInvariantVerificationError(
            f"{field_name} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CriticalInvariantVerificationError(f"{field_name} contains control characters")
    return value


def _git_object_id(value: str, *, field_name: str) -> str:
    normalized = _identifier(value, field_name=field_name)
    if len(normalized) not in (40, 64) or normalized != normalized.lower():
        raise CriticalInvariantVerificationError(
            f"{field_name} must be a lowercase 40- or 64-hex Git object id"
        )
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise CriticalInvariantVerificationError(
            f"{field_name} must be a lowercase 40- or 64-hex Git object id"
        ) from exc
    return normalized


@dataclass(frozen=True, slots=True)
class CriticalInvariantDefinition:
    invariant_id: CriticalInvariantId
    subsystem: str
    verifier_version: str
    statement: str

    def __post_init__(self) -> None:
        _identifier(self.subsystem, field_name="invariant subsystem")
        _identifier(self.verifier_version, field_name="invariant verifier_version")
        _identifier(self.statement, field_name="invariant statement")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "invariant_id": self.invariant_id.value,
            "subsystem": self.subsystem,
            "verifier_version": self.verifier_version,
            "statement": self.statement,
        }


def _reference_definitions() -> tuple[CriticalInvariantDefinition, ...]:
    definitions = (
        CriticalInvariantDefinition(
            CriticalInvariantId.CCL_BUNDLE_INTEGRITY,
            "canonical-case-ledger",
            "iv01.ccl-bundle.v1",
            "Portable CCL bundle verifies exact canonical history and content identity.",
        ),
        CriticalInvariantDefinition(
            CriticalInvariantId.RECOVERY_IDENTITY_EQUIVALENCE,
            "canonical-ledger-recovery",
            "iv01.recovery-equivalence.v1",
            "Verified restored CCL history is exactly identical to its verified source bundle.",
        ),
        CriticalInvariantDefinition(
            CriticalInvariantId.REPLAY_REBUILD_EQUIVALENCE,
            "case-replay-v2",
            "iv01.replay-rebuild.v1",
            "Offline replay rebuild reproduces the manifest-bound projection identities.",
        ),
        CriticalInvariantDefinition(
            CriticalInvariantId.MIGRATION_DETERMINISM,
            "case-migrations",
            "iv01.migration-determinism.v1",
            "An explicit migration path produces the same immutable target on repeated runs.",
        ),
        CriticalInvariantDefinition(
            CriticalInvariantId.EPISTEMIC_REBUILD_EQUIVALENCE,
            "epistemic-v2",
            "iv01.epistemic-rebuild.v1",
            "Epistemic state rebuild is deterministic for the exact case history and policy.",
        ),
        CriticalInvariantDefinition(
            CriticalInvariantId.SEMANTIC_PROPAGATION_BOUNDED,
            "semantic-change-v2",
            "iv01.semantic-bounds.v1",
            "Change propagation is replay-bound and remains within explicit hard budgets.",
        ),
    )
    return tuple(sorted(definitions, key=lambda item: item.invariant_id.value))


@dataclass(frozen=True, slots=True)
class CriticalInvariantRegistry:
    definitions: tuple[CriticalInvariantDefinition, ...]
    registry_identity: ContentAddress
    schema: str = CRITICAL_INVARIANT_REGISTRY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRITICAL_INVARIANT_REGISTRY_SCHEMA_V1:
            raise CriticalInvariantVerificationError(
                f"unsupported critical invariant registry schema: {self.schema}"
            )
        expected = _reference_definitions()
        if self.definitions != expected:
            raise CriticalInvariantVerificationError(
                "critical invariant registry must contain the exact reference invariant set"
            )
        self.verify()

    @classmethod
    def reference(cls) -> CriticalInvariantRegistry:
        definitions = _reference_definitions()
        body = cls._body(definitions)
        return cls(
            definitions=definitions,
            registry_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        definitions: tuple[CriticalInvariantDefinition, ...],
    ) -> dict[str, object]:
        return {
            "schema": CRITICAL_INVARIANT_REGISTRY_SCHEMA_V1,
            "definitions": [item.canonical_dict() for item in definitions],
            "authority": "verification-only",
            "failure_semantics": "fail-closed-no-partial-pass",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(self.definitions)

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "registry_identity": self.registry_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.registry_identity != ContentAddress.for_value(self.canonical_body()):
            raise CriticalInvariantVerificationError(
                "critical invariant registry content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class MigrationInvariantProbe:
    registry: CaseMigrationRegistry
    source: VersionedCase
    target_version: str


@dataclass(frozen=True, slots=True)
class EpistemicInvariantProbe:
    case_id: CaseId
    events: tuple[LedgerEvent, ...]
    policy: EpistemicPolicyV2


@dataclass(frozen=True, slots=True)
class SemanticInvariantProbe:
    graph: SemanticChangeGraphV2
    changed: tuple[ImmutableArtifactRef, ...]
    policy: SemanticPropagationPolicyV2
    replay_manifest_identity: ContentAddress
    materialize_paths: bool = True


@dataclass(frozen=True, slots=True)
class CriticalInvariantInputs:
    ledger_bundle: Mapping[str, object]
    recovery_source_bundle: Mapping[str, object]
    recovery_restored_bundle: Mapping[str, object]
    replay_bundle: Mapping[str, object]
    migration: MigrationInvariantProbe
    epistemic: EpistemicInvariantProbe
    semantic: SemanticInvariantProbe


@dataclass(frozen=True, slots=True)
class CriticalInvariantResult:
    invariant_id: CriticalInvariantId
    evidence_identity: ContentAddress
    result_identity: ContentAddress
    outcome: VerificationOutcome = VerificationOutcome.PASS
    schema: str = CRITICAL_INVARIANT_RESULT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRITICAL_INVARIANT_RESULT_SCHEMA_V1:
            raise CriticalInvariantVerificationError(
                f"unsupported critical invariant result schema: {self.schema}"
            )
        if self.outcome is not VerificationOutcome.PASS:
            raise CriticalInvariantVerificationError("failed invariant cannot enter a PASS report")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        invariant_id: CriticalInvariantId,
        evidence: Mapping[str, object],
    ) -> CriticalInvariantResult:
        evidence_identity = ContentAddress.for_value(
            {
                "schema": "lukart.critical-invariant-evidence.v1",
                "invariant_id": invariant_id.value,
                "evidence": dict(evidence),
            }
        )
        body = cls._body(
            invariant_id=invariant_id,
            evidence_identity=evidence_identity,
        )
        return cls(
            invariant_id=invariant_id,
            evidence_identity=evidence_identity,
            result_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        invariant_id: CriticalInvariantId,
        evidence_identity: ContentAddress,
    ) -> dict[str, object]:
        return {
            "schema": CRITICAL_INVARIANT_RESULT_SCHEMA_V1,
            "invariant_id": invariant_id.value,
            "outcome": VerificationOutcome.PASS.value,
            "evidence_identity": evidence_identity.canonical_dict(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            invariant_id=self.invariant_id,
            evidence_identity=self.evidence_identity,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "result_identity": self.result_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.result_identity != ContentAddress.for_value(self.canonical_body()):
            raise CriticalInvariantVerificationError(
                f"critical invariant result identity mismatch: {self.invariant_id.value}"
            )


@dataclass(frozen=True, slots=True)
class CriticalInvariantVerificationReport:
    code_sha: str
    registry_identity: ContentAddress
    results: tuple[CriticalInvariantResult, ...]
    report_identity: ContentAddress
    outcome: VerificationOutcome = VerificationOutcome.PASS
    schema: str = CRITICAL_INVARIANT_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CRITICAL_INVARIANT_REPORT_SCHEMA_V1:
            raise CriticalInvariantVerificationError(
                f"unsupported critical invariant report schema: {self.schema}"
            )
        _git_object_id(self.code_sha, field_name="code_sha")
        reference = CriticalInvariantRegistry.reference()
        if self.registry_identity != reference.registry_identity:
            raise CriticalInvariantVerificationError("critical invariant registry identity mismatch")
        expected_ids = tuple(item.invariant_id for item in reference.definitions)
        actual_ids = tuple(item.invariant_id for item in self.results)
        if actual_ids != expected_ids:
            raise CriticalInvariantVerificationError(
                "critical invariant report is missing, duplicated or reorders required checks"
            )
        for result in self.results:
            result.verify()
        self.verify()

    @staticmethod
    def _body(
        *,
        code_sha: str,
        registry_identity: ContentAddress,
        results: tuple[CriticalInvariantResult, ...],
    ) -> dict[str, object]:
        return {
            "schema": CRITICAL_INVARIANT_REPORT_SCHEMA_V1,
            "code_sha": code_sha,
            "registry_identity": registry_identity.canonical_dict(),
            "outcome": VerificationOutcome.PASS.value,
            "results": [result.canonical_dict() for result in results],
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            code_sha=self.code_sha,
            registry_identity=self.registry_identity,
            results=self.results,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "report_identity": self.report_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.report_identity != ContentAddress.for_value(self.canonical_body()):
            raise CriticalInvariantVerificationError(
                "critical invariant report content-address mismatch"
            )


def _verify_ccl_bundle(value: Mapping[str, object]) -> Mapping[str, object]:
    bundle = CanonicalCaseLedger.verify_export(value)
    return {
        "case_id": bundle.case_id.value,
        "ledger_head": bundle.head_event_id.canonical_dict() if bundle.head_event_id else None,
        "bundle_digest": bundle.bundle_digest.canonical_dict(),
        "event_count": len(bundle.events),
    }


def _verify_recovery_equivalence(
    source_value: Mapping[str, object],
    restored_value: Mapping[str, object],
) -> Mapping[str, object]:
    source = CanonicalCaseLedger.verify_export(source_value)
    restored = CanonicalCaseLedger.verify_export(restored_value)
    if source != restored:
        raise CriticalInvariantVerificationError(
            "recovery identity mismatch between verified source and restored bundle"
        )
    return {
        "case_id": source.case_id.value,
        "ledger_head": source.head_event_id.canonical_dict() if source.head_event_id else None,
        "bundle_digest": source.bundle_digest.canonical_dict(),
        "event_count": len(source.events),
    }


def _verify_replay(value: Mapping[str, object]) -> Mapping[str, object]:
    verification = verify_case_replay_bundle(value)
    return {
        "manifest_identity": verification.manifest_identity.canonical_dict(),
        "ledger_head": (
            verification.ledger_head.canonical_dict() if verification.ledger_head else None
        ),
        "epistemic_projection_identity": (
            verification.epistemic_projection_identity.canonical_dict()
        ),
        "trust_graph_identity": verification.trust_graph_identity.canonical_dict(),
        "runtime_identity_digest": verification.runtime_identity_digest.canonical_dict(),
    }


def _verify_migration(probe: MigrationInvariantProbe) -> Mapping[str, object]:
    first = probe.registry.migrate(probe.source, probe.target_version)
    second = probe.registry.migrate(probe.source, probe.target_version)
    if (
        first.path != second.path
        or first.path_digest != second.path_digest
        or first.target.payload_digest != second.target.payload_digest
    ):
        raise CriticalInvariantVerificationError("migration repeated-run equivalence mismatch")
    return {
        "registry_digest": probe.registry.digest(),
        "source_payload_digest": probe.source.payload_digest,
        "target_payload_digest": first.target.payload_digest,
        "path": list(first.path),
        "path_digest": first.path_digest,
    }


def _verify_epistemic(probe: EpistemicInvariantProbe) -> Mapping[str, object]:
    first = EpistemicProjectionV2.build(
        case_id=probe.case_id,
        events=probe.events,
        policy=probe.policy,
    )
    second = EpistemicProjectionV2.build(
        case_id=probe.case_id,
        events=probe.events,
        policy=probe.policy,
    )
    first.verify()
    second.verify()
    if first.projection_identity != second.projection_identity:
        raise CriticalInvariantVerificationError("epistemic repeated rebuild identity mismatch")
    return {
        "case_id": probe.case_id.value,
        "ledger_head": first.ledger_head.canonical_dict() if first.ledger_head else None,
        "policy_identity": probe.policy.policy_identity.canonical_dict(),
        "projection_identity": first.projection_identity.canonical_dict(),
    }


def _verify_semantic(probe: SemanticInvariantProbe) -> Mapping[str, object]:
    first = probe.graph.plan(
        probe.changed,
        policy=probe.policy,
        replay_manifest_identity=probe.replay_manifest_identity,
        materialize_paths=probe.materialize_paths,
    )
    second = probe.graph.plan(
        probe.changed,
        policy=probe.policy,
        replay_manifest_identity=probe.replay_manifest_identity,
        materialize_paths=probe.materialize_paths,
    )
    first.verify()
    second.verify()
    first.require_replay_manifest(probe.replay_manifest_identity)
    if first.plan_identity != second.plan_identity:
        raise CriticalInvariantVerificationError("semantic repeated plan identity mismatch")
    if (
        len(first.affected) > probe.policy.max_nodes
        or first.max_depth_observed > probe.policy.max_depth
        or first.work_count > probe.policy.max_work
    ):
        raise CriticalInvariantVerificationError("semantic propagation escaped hard budgets")
    return {
        "case_id": probe.graph.case_id.value,
        "graph_identity": probe.graph.graph_identity.canonical_dict(),
        "policy_identity": probe.policy.policy_identity.canonical_dict(),
        "replay_manifest_identity": probe.replay_manifest_identity.canonical_dict(),
        "plan_identity": first.plan_identity.canonical_dict(),
        "affected_count": len(first.affected),
        "max_depth_observed": first.max_depth_observed,
        "work_count": first.work_count,
    }


def _run_invariant(
    invariant_id: CriticalInvariantId,
    inputs: CriticalInvariantInputs,
) -> CriticalInvariantResult:
    try:
        if invariant_id is CriticalInvariantId.CCL_BUNDLE_INTEGRITY:
            evidence = _verify_ccl_bundle(inputs.ledger_bundle)
        elif invariant_id is CriticalInvariantId.RECOVERY_IDENTITY_EQUIVALENCE:
            evidence = _verify_recovery_equivalence(
                inputs.recovery_source_bundle,
                inputs.recovery_restored_bundle,
            )
        elif invariant_id is CriticalInvariantId.REPLAY_REBUILD_EQUIVALENCE:
            evidence = _verify_replay(inputs.replay_bundle)
        elif invariant_id is CriticalInvariantId.MIGRATION_DETERMINISM:
            evidence = _verify_migration(inputs.migration)
        elif invariant_id is CriticalInvariantId.EPISTEMIC_REBUILD_EQUIVALENCE:
            evidence = _verify_epistemic(inputs.epistemic)
        elif invariant_id is CriticalInvariantId.SEMANTIC_PROPAGATION_BOUNDED:
            evidence = _verify_semantic(inputs.semantic)
        else:
            raise CriticalInvariantVerificationError(
                f"unregistered critical invariant: {invariant_id}"
            )
    except CriticalInvariantVerificationError:
        raise
    except Exception as exc:
        raise CriticalInvariantVerificationError(
            f"critical invariant failed: {invariant_id.value}: {exc}"
        ) from exc
    return CriticalInvariantResult.build(
        invariant_id=invariant_id,
        evidence=evidence,
    )


def verify_critical_invariants(
    *,
    code_sha: str,
    expected_code_sha: str,
    inputs: CriticalInvariantInputs,
) -> CriticalInvariantVerificationReport:
    """Run the complete reference invariant set or fail without a partial PASS report.

    ``expected_code_sha`` is supplied by the exact-SHA execution boundary (for example,
    CI/PR-head validation). A mismatch is rejected before any invariant is evaluated.
    """

    actual_sha = _git_object_id(code_sha, field_name="code_sha")
    expected_sha = _git_object_id(expected_code_sha, field_name="expected_code_sha")
    if actual_sha != expected_sha:
        raise CriticalInvariantVerificationError(
            "critical invariant verification code SHA does not match expected exact SHA"
        )

    registry = CriticalInvariantRegistry.reference()
    results = tuple(
        _run_invariant(definition.invariant_id, inputs)
        for definition in registry.definitions
    )
    body = CriticalInvariantVerificationReport._body(
        code_sha=actual_sha,
        registry_identity=registry.registry_identity,
        results=results,
    )
    return CriticalInvariantVerificationReport(
        code_sha=actual_sha,
        registry_identity=registry.registry_identity,
        results=results,
        report_identity=ContentAddress.for_value(body),
    )
