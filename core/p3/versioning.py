"""P3-03/H5 explicit case schema versioning, deterministic migrations and replay comparison."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.p2.semantic import SemanticDiff, semantic_diff

from .contracts import (
    P3ContractError,
    ReplayComparison,
    ReplayRelation,
    RuntimeIdentity,
    content_digest,
)


@dataclass(frozen=True, slots=True)
class VersionedCase:
    case_id: str
    schema_version: str
    payload: Mapping[str, object]
    payload_digest: str

    @classmethod
    def build(
        cls, *, case_id: str, schema_version: str, payload: Mapping[str, object]
    ) -> VersionedCase:
        case_id = case_id.strip()
        schema_version = schema_version.strip()
        if not case_id or not schema_version:
            raise P3ContractError("case_id and schema_version are required")
        copied = json.loads(json.dumps(dict(payload), ensure_ascii=False))
        if not isinstance(copied, dict):
            raise P3ContractError("case payload must be an object")
        return cls(case_id, schema_version, copied, content_digest(copied))

    def verify(self) -> None:
        if self.payload_digest != content_digest(self.payload):
            raise P3ContractError("case payload digest mismatch")


MigrationFunction = Callable[[Mapping[str, object]], Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class MigrationStep:
    source_version: str
    target_version: str
    migrate: MigrationFunction


@dataclass(frozen=True, slots=True)
class MigrationReport:
    source: VersionedCase
    target: VersionedCase
    path: tuple[str, ...]
    semantic: SemanticDiff

    @property
    def changed_semantics(self) -> bool:
        return self.semantic.changed

    @property
    def path_digest(self) -> str:
        return content_digest(
            {
                "schema": "lukart.migration-path.v1",
                "path": list(self.path),
                "source_payload_digest": self.source.payload_digest,
                "target_payload_digest": self.target.payload_digest,
            }
        )


class CaseMigrationRegistry:
    """Explicit deterministic migration graph; unknown or ambiguous upgrades fail closed."""

    def __init__(self) -> None:
        self._steps: dict[tuple[str, str], MigrationStep] = {}

    def register(self, step: MigrationStep) -> None:
        source = step.source_version.strip()
        target = step.target_version.strip()
        if not source or not target or source == target:
            raise P3ContractError("migration requires distinct nonblank versions")
        key = (source, target)
        if key in self._steps:
            raise P3ContractError(f"duplicate migration: {source}->{target}")
        self._steps[key] = MigrationStep(source, target, step.migrate)

    def _all_paths(self, source: str, target: str) -> tuple[tuple[str, ...], ...]:
        adjacency: dict[str, list[str]] = {}
        vertices: set[str] = {source, target}
        for left, right in self._steps:
            adjacency.setdefault(left, []).append(right)
            vertices.update((left, right))
        for values in adjacency.values():
            values.sort()

        routes: list[tuple[str, ...]] = []

        def visit(current: str, route: tuple[str, ...]) -> None:
            if len(route) > len(vertices):
                return
            if current == target:
                routes.append(route)
                return
            for neighbor in adjacency.get(current, []):
                if neighbor in route:
                    continue
                visit(neighbor, (*route, neighbor))
                if len(routes) > 1:
                    return

        visit(source, (source,))
        return tuple(routes)

    def path(self, source: str, target: str) -> tuple[str, ...]:
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise P3ContractError("migration versions cannot be blank")
        if source == target:
            return (source,)
        routes = self._all_paths(source, target)
        if not routes:
            raise P3ContractError(f"no migration path: {source}->{target}")
        if len(routes) > 1:
            raise P3ContractError(f"ambiguous migration path: {source}->{target}")
        return routes[0]

    def _run_route(
        self, source_payload: Mapping[str, object], route: tuple[str, ...]
    ) -> Mapping[str, object]:
        payload: Mapping[str, object] = dict(source_payload)
        for index in range(len(route) - 1):
            left = route[index]
            right = route[index + 1]
            step = self._steps[(left, right)]
            source_copy = json.loads(json.dumps(dict(payload), ensure_ascii=False))
            result = step.migrate(source_copy)
            if not isinstance(result, Mapping):
                raise P3ContractError(f"migration {left}->{right} returned non-mapping")
            payload = dict(result)
        return payload

    def migrate(self, case: VersionedCase, target_version: str) -> MigrationReport:
        case.verify()
        route = self.path(case.schema_version, target_version)
        if len(route) == 1:
            return MigrationReport(case, case, route, semantic_diff(case.payload, case.payload))

        original_digest = case.payload_digest
        payload = self._run_route(case.payload, route)

        case.verify()
        if case.payload_digest != original_digest:
            raise P3ContractError("migration mutated source case")

        target = VersionedCase.build(
            case_id=case.case_id,
            schema_version=target_version,
            payload=payload,
        )

        replay_payload = self._run_route(case.payload, route)
        if content_digest(replay_payload) != target.payload_digest:
            raise P3ContractError("non-deterministic migration detected")

        return MigrationReport(
            source=case,
            target=target,
            path=route,
            semantic=semantic_diff(case.payload, target.payload),
        )

    def compare_replay(
        self,
        baseline: RuntimeIdentity,
        candidate: RuntimeIdentity,
        *,
        migration_report: MigrationReport | None = None,
    ) -> ReplayComparison:
        """Classify replay identity without hiding missing identity or semantic divergence."""

        missing = tuple(
            sorted(
                {
                    *(f"baseline.{name}" for name in baseline.incomplete_fields()),
                    *(f"candidate.{name}" for name in candidate.incomplete_fields()),
                }
            )
        )
        differences = baseline.differing_fields(candidate)
        if missing:
            return ReplayComparison(
                relation=ReplayRelation.INCOMPLETE,
                baseline_identity_digest=baseline.digest(),
                candidate_identity_digest=candidate.digest(),
                differing_fields=differences,
                unresolved=missing,
            )

        if baseline.digest() == candidate.digest():
            return ReplayComparison(
                relation=ReplayRelation.IDENTICAL,
                baseline_identity_digest=baseline.digest(),
                candidate_identity_digest=candidate.digest(),
                differing_fields=(),
                semantic_divergence=False,
            )

        if baseline.schema_version != candidate.schema_version:
            route = self.path(baseline.schema_version, candidate.schema_version)
            semantic_divergence: bool | None = None
            unresolved: tuple[str, ...] = ("semantic_divergence_unmeasured",)
            if migration_report is not None:
                expected_pair = (
                    migration_report.source.schema_version,
                    migration_report.target.schema_version,
                )
                if expected_pair != (baseline.schema_version, candidate.schema_version):
                    raise P3ContractError("migration report does not match replay identity versions")
                if migration_report.path != route:
                    raise P3ContractError("migration report path does not match registry path")
                semantic_divergence = migration_report.changed_semantics
                unresolved = ()
            return ReplayComparison(
                relation=ReplayRelation.CROSS_VERSION_COMPARABLE,
                baseline_identity_digest=baseline.digest(),
                candidate_identity_digest=candidate.digest(),
                differing_fields=differences,
                migration_path=route,
                semantic_divergence=semantic_divergence,
                unresolved=unresolved,
            )

        return ReplayComparison(
            relation=ReplayRelation.DIFFERENT,
            baseline_identity_digest=baseline.digest(),
            candidate_identity_digest=candidate.digest(),
            differing_fields=differences,
            semantic_divergence=None,
        )
