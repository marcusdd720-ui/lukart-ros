"""P2 semantic regression, blast-radius and cross-version replay primitives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence


class SemanticSeverity(StrEnum):
    NONE = "NONE"
    MATERIAL = "MATERIAL"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class SemanticChange:
    path: str
    before: object
    after: object
    severity: SemanticSeverity


@dataclass(frozen=True, slots=True)
class SemanticDiff:
    changes: tuple[SemanticChange, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    @property
    def highest_severity(self) -> SemanticSeverity:
        if any(change.severity is SemanticSeverity.CRITICAL for change in self.changes):
            return SemanticSeverity.CRITICAL
        if self.changes:
            return SemanticSeverity.MATERIAL
        return SemanticSeverity.NONE


_CRITICAL_ROOTS = frozenset(
    {
        "decision",
        "status",
        "evidence_refs",
        "support_ids",
        "open_questions",
        "contradictions",
        "certainty",
        "outcome",
    }
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _severity(path: str) -> SemanticSeverity:
    normalized = path.replace("[", ".").replace("]", "")
    parts = tuple(part for part in normalized.split(".") if part)
    if any(part in _CRITICAL_ROOTS for part in parts):
        return SemanticSeverity.CRITICAL
    return SemanticSeverity.MATERIAL


def _diff(before: object, after: object, path: str, changes: list[SemanticChange]) -> None:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        keys = sorted(set(before) | set(after), key=str)
        for key in keys:
            child = f"{path}.{key}" if path else str(key)
            _diff(before.get(key), after.get(key), child, changes)
        return

    if isinstance(before, (list, tuple)) and isinstance(after, (list, tuple)):
        maximum = max(len(before), len(after))
        for index in range(maximum):
            left = before[index] if index < len(before) else None
            right = after[index] if index < len(after) else None
            _diff(left, right, f"{path}[{index}]", changes)
        return

    if before != after:
        changes.append(
            SemanticChange(
                path=path or "$",
                before=before,
                after=after,
                severity=_severity(path),
            )
        )


def semantic_diff(before: Mapping[str, object], after: Mapping[str, object]) -> SemanticDiff:
    changes: list[SemanticChange] = []
    _diff(before, after, "", changes)
    ordered = tuple(sorted(changes, key=lambda item: item.path))
    return SemanticDiff(ordered)


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    """Directed dependency graph: key depends on the listed prerequisite artifacts."""

    dependencies: Mapping[str, Sequence[str]]

    def blast_radius(self, changed_artifact_ids: Sequence[str]) -> tuple[str, ...]:
        reverse: dict[str, set[str]] = {}
        known = set(self.dependencies)
        for artifact_id, prerequisites in self.dependencies.items():
            for prerequisite in prerequisites:
                known.add(prerequisite)
                reverse.setdefault(prerequisite, set()).add(artifact_id)

        affected = {item for item in changed_artifact_ids if item in known}
        pending = list(sorted(affected))
        while pending:
            current = pending.pop()
            for dependent in sorted(reverse.get(current, ())):
                if dependent not in affected:
                    affected.add(dependent)
                    pending.append(dependent)
        return tuple(sorted(affected))


@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    version: str
    code_sha: str
    input_digest: str
    output_digest: str
    output: Mapping[str, object]

    @classmethod
    def build(
        cls,
        *,
        version: str,
        code_sha: str,
        input_payload: object,
        output: Mapping[str, object],
    ) -> ReplaySnapshot:
        if not version.strip() or not code_sha.strip():
            raise ValueError("version and code_sha are required")
        return cls(
            version=version.strip(),
            code_sha=code_sha.strip(),
            input_digest=digest(input_payload),
            output_digest=digest(output),
            output=dict(output),
        )


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    same_input: bool
    byte_equivalent_output: bool
    semantic: SemanticDiff

    @property
    def requires_review(self) -> bool:
        return (not self.same_input) or self.semantic.changed


def compare_replays(left: ReplaySnapshot, right: ReplaySnapshot) -> ReplayComparison:
    return ReplayComparison(
        same_input=left.input_digest == right.input_digest,
        byte_equivalent_output=left.output_digest == right.output_digest,
        semantic=semantic_diff(left.output, right.output),
    )
