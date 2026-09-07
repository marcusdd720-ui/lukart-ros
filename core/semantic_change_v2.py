"""PHX-06 bounded semantic change propagation over exact immutable identities.

This module is a deterministic planning/projection layer. It adds no persistence or
Product write authority. Canonical Case Ledger remains the only writable case-history
SSOT and Case Replay v2 supplies the exact replay identity bound into each plan.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.case_ledger.contracts import CaseId, ContentAddress
from core.p3.contracts import canonical_json
from core.p3.semantic_graph import SemanticChangeGraph

SEMANTIC_PROPAGATION_POLICY_SCHEMA_V2 = "lukart.semantic-propagation-policy.v2"
SEMANTIC_PROPAGATION_PLAN_SCHEMA_V2 = "lukart.semantic-propagation-plan.v2"
RECOMPUTE_LINEAGE_SCHEMA_V2 = "lukart.recompute-lineage.v2"


class SemanticChangeV2Error(ValueError):
    """Fail-closed semantic propagation contract violation."""


class BlastRadiusReason(StrEnum):
    NODES = "NODES"
    DEPTH = "DEPTH"
    WORK = "WORK"


class BlastRadiusExceeded(SemanticChangeV2Error):
    """Hard failure when deterministic propagation exceeds an explicit budget."""

    def __init__(self, reason: BlastRadiusReason, *, observed: int, limit: int) -> None:
        self.reason = reason
        self.observed = observed
        self.limit = limit
        super().__init__(
            f"BLAST_RADIUS_EXCEEDED:{reason.value}:observed={observed}:limit={limit}"
        )


class ArtifactKind(StrEnum):
    EVENT = "EVENT"
    REVISION = "REVISION"
    EVIDENCE = "EVIDENCE"
    PROJECTION = "PROJECTION"
    RESULT = "RESULT"


@dataclass(frozen=True, slots=True)
class ImmutableArtifactRef:
    """Case-scoped reference to one exact immutable content identity."""

    case_id: CaseId
    kind: ArtifactKind
    identity: ContentAddress

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id.value,
            "kind": self.kind.value,
            "identity": self.identity.canonical_dict(),
        }

    @property
    def node_key(self) -> str:
        return canonical_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class SemanticPropagationPolicyV2:
    max_nodes: int
    max_depth: int
    max_work: int
    policy_identity: ContentAddress
    schema: str = SEMANTIC_PROPAGATION_POLICY_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != SEMANTIC_PROPAGATION_POLICY_SCHEMA_V2:
            raise SemanticChangeV2Error(
                f"unsupported semantic propagation policy schema: {self.schema}"
            )
        for name, value in (
            ("max_nodes", self.max_nodes),
            ("max_depth", self.max_depth),
            ("max_work", self.max_work),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise SemanticChangeV2Error(f"{name} must be a positive integer")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        max_nodes: int = 10_000,
        max_depth: int = 256,
        max_work: int = 100_000,
    ) -> SemanticPropagationPolicyV2:
        body = cls._body(
            max_nodes=max_nodes,
            max_depth=max_depth,
            max_work=max_work,
        )
        return cls(
            max_nodes=max_nodes,
            max_depth=max_depth,
            max_work=max_work,
            policy_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(*, max_nodes: int, max_depth: int, max_work: int) -> dict[str, object]:
        return {
            "schema": SEMANTIC_PROPAGATION_POLICY_SCHEMA_V2,
            "max_nodes": max_nodes,
            "max_depth": max_depth,
            "max_work": max_work,
            "overflow_semantics": "hard-fail-no-truncation",
            "authority": "projection-only",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            max_nodes=self.max_nodes,
            max_depth=self.max_depth,
            max_work=self.max_work,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "policy_identity": self.policy_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.policy_identity != ContentAddress.for_value(self.canonical_body()):
            raise SemanticChangeV2Error("semantic propagation policy identity mismatch")


@dataclass(frozen=True, slots=True)
class PropagationPathV2:
    changed: ImmutableArtifactRef
    affected: ImmutableArtifactRef
    path: tuple[ImmutableArtifactRef, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "changed": self.changed.canonical_dict(),
            "affected": self.affected.canonical_dict(),
            "path": [item.canonical_dict() for item in self.path],
        }


@dataclass(frozen=True, slots=True)
class SemanticPropagationPlanV2:
    case_id: CaseId
    changed: tuple[ImmutableArtifactRef, ...]
    affected: tuple[ImmutableArtifactRef, ...]
    paths: tuple[PropagationPathV2, ...]
    graph_identity: ContentAddress
    policy_identity: ContentAddress
    replay_manifest_identity: ContentAddress
    work_count: int
    max_depth_observed: int
    plan_identity: ContentAddress
    schema: str = SEMANTIC_PROPAGATION_PLAN_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != SEMANTIC_PROPAGATION_PLAN_SCHEMA_V2:
            raise SemanticChangeV2Error(f"unsupported propagation plan schema: {self.schema}")
        if not self.changed or not self.affected:
            raise SemanticChangeV2Error("propagation plan requires changed and affected refs")
        if self.work_count < 0 or self.max_depth_observed < 0:
            raise SemanticChangeV2Error("propagation counters cannot be negative")
        for ref in (*self.changed, *self.affected):
            if ref.case_id != self.case_id:
                raise SemanticChangeV2Error("propagation plan contains cross-case artifact")
        self.verify()

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": SEMANTIC_PROPAGATION_PLAN_SCHEMA_V2,
            "case_id": self.case_id.value,
            "changed": [item.canonical_dict() for item in self.changed],
            "affected": [item.canonical_dict() for item in self.affected],
            "paths": [item.canonical_dict() for item in self.paths],
            "graph_identity": self.graph_identity.canonical_dict(),
            "policy_identity": self.policy_identity.canonical_dict(),
            "replay_manifest_identity": self.replay_manifest_identity.canonical_dict(),
            "work_count": self.work_count,
            "max_depth_observed": self.max_depth_observed,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "plan_identity": self.plan_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.plan_identity != ContentAddress.for_value(self.canonical_body()):
            raise SemanticChangeV2Error("semantic propagation plan identity mismatch")

    def require_replay_manifest(self, identity: ContentAddress) -> None:
        if identity != self.replay_manifest_identity:
            raise SemanticChangeV2Error("semantic propagation replay identity mismatch")


class SemanticChangeGraphV2:
    """Typed, case-scoped and budgeted projection over existing P3 graph semantics."""

    def __init__(
        self,
        *,
        case_id: CaseId,
        dependencies: Mapping[
            ImmutableArtifactRef,
            Sequence[ImmutableArtifactRef],
        ],
    ) -> None:
        normalized: dict[ImmutableArtifactRef, tuple[ImmutableArtifactRef, ...]] = {}
        known: set[ImmutableArtifactRef] = set()
        for artifact, prerequisites in dependencies.items():
            self._require_case(artifact, case_id)
            prerequisite_tuple = tuple(prerequisites)
            for prerequisite in prerequisite_tuple:
                self._require_case(prerequisite, case_id)
            if artifact in prerequisite_tuple:
                raise SemanticChangeV2Error("self dependency is forbidden")
            if len(prerequisite_tuple) != len(set(prerequisite_tuple)):
                raise SemanticChangeV2Error("duplicate immutable prerequisite")
            normalized[artifact] = tuple(
                sorted(prerequisite_tuple, key=lambda item: item.node_key)
            )
            known.add(artifact)
            known.update(prerequisite_tuple)

        if not known:
            raise SemanticChangeV2Error("semantic graph cannot be empty")
        for artifact in known:
            normalized.setdefault(artifact, ())

        self.case_id = case_id
        self._dependencies = dict(
            sorted(normalized.items(), key=lambda item: item[0].node_key)
        )
        self._by_key = {artifact.node_key: artifact for artifact in self._dependencies}
        key_dependencies = {
            artifact.node_key: tuple(item.node_key for item in prerequisites)
            for artifact, prerequisites in self._dependencies.items()
        }
        legacy = SemanticChangeGraph(key_dependencies)
        legacy.validate_acyclic()
        self._reverse = self._build_reverse()
        self.graph_identity = ContentAddress.for_value(self.canonical_body())

    @staticmethod
    def _require_case(ref: ImmutableArtifactRef, case_id: CaseId) -> None:
        if ref.case_id != case_id:
            raise SemanticChangeV2Error("cross-case semantic dependency is forbidden")

    def _build_reverse(self) -> dict[ImmutableArtifactRef, tuple[ImmutableArtifactRef, ...]]:
        reverse: dict[ImmutableArtifactRef, set[ImmutableArtifactRef]] = {
            key: set() for key in self._dependencies
        }
        for dependent, prerequisites in self._dependencies.items():
            for prerequisite in prerequisites:
                reverse.setdefault(prerequisite, set()).add(dependent)
        return {
            key: tuple(sorted(values, key=lambda item: item.node_key))
            for key, values in reverse.items()
        }

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": "lukart.semantic-change-graph.v2",
            "case_id": self.case_id.value,
            "dependencies": [
                {
                    "artifact": artifact.canonical_dict(),
                    "prerequisites": [item.canonical_dict() for item in prerequisites],
                }
                for artifact, prerequisites in self._dependencies.items()
            ],
        }

    def plan(
        self,
        changed: Sequence[ImmutableArtifactRef],
        *,
        policy: SemanticPropagationPolicyV2,
        replay_manifest_identity: ContentAddress,
        materialize_paths: bool = True,
    ) -> SemanticPropagationPlanV2:
        policy.verify()
        changed_tuple = tuple(sorted(set(changed), key=lambda item: item.node_key))
        if not changed_tuple:
            raise SemanticChangeV2Error("changed refs cannot be empty")
        for ref in changed_tuple:
            self._require_case(ref, self.case_id)
            if ref not in self._dependencies:
                raise SemanticChangeV2Error(f"unknown changed immutable ref: {ref.node_key}")

        affected: set[ImmutableArtifactRef] = set()
        path_records: dict[tuple[str, str], tuple[ImmutableArtifactRef, ...]] = {}
        work_count = 0
        max_depth_observed = 0

        for root in changed_tuple:
            queue: deque[
                tuple[ImmutableArtifactRef, int, tuple[ImmutableArtifactRef, ...] | None]
            ] = deque([(root, 0, (root,) if materialize_paths else None)])
            seen: set[ImmutableArtifactRef] = set()
            while queue:
                current, depth, path = queue.popleft()
                if current in seen:
                    continue
                seen.add(current)
                max_depth_observed = max(max_depth_observed, depth)

                if current not in affected and len(affected) + 1 > policy.max_nodes:
                    raise BlastRadiusExceeded(
                        BlastRadiusReason.NODES,
                        observed=len(affected) + 1,
                        limit=policy.max_nodes,
                    )
                affected.add(current)
                if materialize_paths:
                    if path is None:
                        raise SemanticChangeV2Error("internal path materialization violation")
                    path_records[(root.node_key, current.node_key)] = path

                dependents = self._reverse.get(current, ())
                if dependents and depth >= policy.max_depth:
                    raise BlastRadiusExceeded(
                        BlastRadiusReason.DEPTH,
                        observed=depth + 1,
                        limit=policy.max_depth,
                    )
                for dependent in dependents:
                    work_count += 1
                    if work_count > policy.max_work:
                        raise BlastRadiusExceeded(
                            BlastRadiusReason.WORK,
                            observed=work_count,
                            limit=policy.max_work,
                        )
                    if dependent in seen:
                        continue
                    next_path = (*path, dependent) if path is not None else None
                    queue.append((dependent, depth + 1, next_path))

        affected_tuple = tuple(sorted(affected, key=lambda item: item.node_key))
        paths = tuple(
            PropagationPathV2(
                changed=self._by_key[root_key],
                affected=self._by_key[affected_key],
                path=path,
            )
            for (root_key, affected_key), path in sorted(path_records.items())
        )
        body = {
            "schema": SEMANTIC_PROPAGATION_PLAN_SCHEMA_V2,
            "case_id": self.case_id.value,
            "changed": [item.canonical_dict() for item in changed_tuple],
            "affected": [item.canonical_dict() for item in affected_tuple],
            "paths": [item.canonical_dict() for item in paths],
            "graph_identity": self.graph_identity.canonical_dict(),
            "policy_identity": policy.policy_identity.canonical_dict(),
            "replay_manifest_identity": replay_manifest_identity.canonical_dict(),
            "work_count": work_count,
            "max_depth_observed": max_depth_observed,
        }
        return SemanticPropagationPlanV2(
            case_id=self.case_id,
            changed=changed_tuple,
            affected=affected_tuple,
            paths=paths,
            graph_identity=self.graph_identity,
            policy_identity=policy.policy_identity,
            replay_manifest_identity=replay_manifest_identity,
            work_count=work_count,
            max_depth_observed=max_depth_observed,
            plan_identity=ContentAddress.for_value(body),
        )


@dataclass(frozen=True, slots=True)
class RecomputeLineageV2:
    plan_identity: ContentAddress
    replay_manifest_identity: ContentAddress
    previous_result_identity: ContentAddress
    content_identity: ContentAddress
    result_identity: ContentAddress
    schema: str = RECOMPUTE_LINEAGE_SCHEMA_V2

    @classmethod
    def build(
        cls,
        *,
        plan: SemanticPropagationPlanV2,
        previous_result_identity: ContentAddress,
        output: object,
    ) -> RecomputeLineageV2:
        plan.verify()
        content_identity = ContentAddress.for_value(output)
        body = {
            "schema": RECOMPUTE_LINEAGE_SCHEMA_V2,
            "plan_identity": plan.plan_identity.canonical_dict(),
            "replay_manifest_identity": plan.replay_manifest_identity.canonical_dict(),
            "previous_result_identity": previous_result_identity.canonical_dict(),
            "content_identity": content_identity.canonical_dict(),
        }
        result_identity = ContentAddress.for_value(body)
        if result_identity == previous_result_identity:
            raise SemanticChangeV2Error("recompute result identity cannot equal previous result")
        return cls(
            plan_identity=plan.plan_identity,
            replay_manifest_identity=plan.replay_manifest_identity,
            previous_result_identity=previous_result_identity,
            content_identity=content_identity,
            result_identity=result_identity,
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": RECOMPUTE_LINEAGE_SCHEMA_V2,
            "plan_identity": self.plan_identity.canonical_dict(),
            "replay_manifest_identity": self.replay_manifest_identity.canonical_dict(),
            "previous_result_identity": self.previous_result_identity.canonical_dict(),
            "content_identity": self.content_identity.canonical_dict(),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "result_identity": self.result_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.result_identity != ContentAddress.for_value(self.canonical_body()):
            raise SemanticChangeV2Error("recompute lineage result identity mismatch")
