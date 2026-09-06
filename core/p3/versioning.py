"""P3-03 explicit case schema versioning and deterministic migrations."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.p2.semantic import SemanticDiff, semantic_diff

from .contracts import P3ContractError, content_digest


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


class CaseMigrationRegistry:
    """Explicit, deterministic migration graph; no implicit schema upgrades."""

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

    def path(self, source: str, target: str) -> tuple[str, ...]:
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise P3ContractError("migration versions cannot be blank")
        if source == target:
            return (source,)
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(source, (source,))])
        visited: set[str] = set()
        adjacency: dict[str, list[str]] = {}
        for left, right in self._steps:
            adjacency.setdefault(left, []).append(right)
        for values in adjacency.values():
            values.sort()
        while queue:
            current, route = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for neighbor in adjacency.get(current, []):
                next_route = (*route, neighbor)
                if neighbor == target:
                    return next_route
                queue.append((neighbor, next_route))
        raise P3ContractError(f"no migration path: {source}->{target}")

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
