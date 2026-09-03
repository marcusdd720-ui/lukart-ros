"""Versioning and migration compatibility contracts for release-managed artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> SchemaVersion:
        match = _VERSION_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError("schema version must use MAJOR.MINOR.PATCH")
        return cls(*(int(item) for item in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    MIGRATION_REQUIRED = "migration_required"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True, slots=True)
class CompatibilityDecision:
    status: CompatibilityStatus
    reader_version: SchemaVersion
    artifact_version: SchemaVersion
    reason: str


def evaluate_schema_compatibility(
    reader_version: SchemaVersion,
    artifact_version: SchemaVersion,
) -> CompatibilityDecision:
    """Apply the release policy: same-major older/equal artifacts are directly readable."""

    if artifact_version.major != reader_version.major:
        return CompatibilityDecision(
            CompatibilityStatus.INCOMPATIBLE,
            reader_version,
            artifact_version,
            "major schema versions differ; explicit migration path is required",
        )
    if artifact_version <= reader_version:
        return CompatibilityDecision(
            CompatibilityStatus.COMPATIBLE,
            reader_version,
            artifact_version,
            "reader supports this same-major artifact version",
        )
    return CompatibilityDecision(
        CompatibilityStatus.MIGRATION_REQUIRED,
        reader_version,
        artifact_version,
        "artifact is newer than the reader within the same major version",
    )


@dataclass(frozen=True, slots=True, order=True)
class MigrationStep:
    migration_id: str
    artifact_type: str
    from_version: SchemaVersion
    to_version: SchemaVersion
    reversible: bool

    def __post_init__(self) -> None:
        for field_name in ("migration_id", "artifact_type"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} cannot be blank")
            object.__setattr__(self, field_name, value)
        if self.from_version == self.to_version:
            raise ValueError("migration must change schema version")


class MigrationRegistry:
    """Deterministic registry; duplicate migration edges are rejected."""

    def __init__(self, steps: tuple[MigrationStep, ...]) -> None:
        ids = [step.migration_id for step in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("migration ids must be unique")
        edges = [
            (step.artifact_type, step.from_version, step.to_version)
            for step in steps
        ]
        if len(edges) != len(set(edges)):
            raise ValueError("migration edges must be unique")
        self._steps = tuple(sorted(steps))

    def direct_migration(
        self,
        artifact_type: str,
        from_version: SchemaVersion,
        to_version: SchemaVersion,
    ) -> MigrationStep | None:
        artifact = artifact_type.strip()
        for step in self._steps:
            if (
                step.artifact_type == artifact
                and step.from_version == from_version
                and step.to_version == to_version
            ):
                return step
        return None
