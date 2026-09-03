from __future__ import annotations

import pytest

from validation.schema_compatibility import (
    CompatibilityStatus,
    MigrationRegistry,
    MigrationStep,
    SchemaVersion,
    evaluate_schema_compatibility,
)


def test_same_major_older_artifact_is_compatible() -> None:
    decision = evaluate_schema_compatibility(
        SchemaVersion.parse("1.3.0"),
        SchemaVersion.parse("1.1.5"),
    )

    assert decision.status is CompatibilityStatus.COMPATIBLE


def test_newer_same_major_artifact_requires_migration_or_reader_upgrade() -> None:
    decision = evaluate_schema_compatibility(
        SchemaVersion.parse("1.2.0"),
        SchemaVersion.parse("1.3.0"),
    )

    assert decision.status is CompatibilityStatus.MIGRATION_REQUIRED


def test_major_mismatch_is_incompatible_without_explicit_migration() -> None:
    decision = evaluate_schema_compatibility(
        SchemaVersion.parse("1.9.0"),
        SchemaVersion.parse("2.0.0"),
    )

    assert decision.status is CompatibilityStatus.INCOMPATIBLE


def test_migration_registry_resolves_only_declared_edge() -> None:
    step = MigrationStep(
        migration_id="case-replay-1-to-2",
        artifact_type="case-replay",
        from_version=SchemaVersion.parse("1.0.0"),
        to_version=SchemaVersion.parse("2.0.0"),
        reversible=True,
    )
    registry = MigrationRegistry((step,))

    assert registry.direct_migration(
        "case-replay",
        SchemaVersion.parse("1.0.0"),
        SchemaVersion.parse("2.0.0"),
    ) == step
    assert registry.direct_migration(
        "case-replay",
        SchemaVersion.parse("1.0.0"),
        SchemaVersion.parse("1.1.0"),
    ) is None


def test_invalid_versions_and_duplicate_migrations_fail_closed() -> None:
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        SchemaVersion.parse("v1")

    first = MigrationStep(
        "migration-a",
        "result",
        SchemaVersion.parse("1.0.0"),
        SchemaVersion.parse("2.0.0"),
        False,
    )
    duplicate_edge = MigrationStep(
        "migration-b",
        "result",
        SchemaVersion.parse("1.0.0"),
        SchemaVersion.parse("2.0.0"),
        False,
    )
    with pytest.raises(ValueError, match="edges must be unique"):
        MigrationRegistry((first, duplicate_edge))
