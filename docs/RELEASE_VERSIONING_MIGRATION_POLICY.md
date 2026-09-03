# LUKART Release, Versioning, and Migration Policy

Status: IMPLEMENTED POLICY / PRODUCTION VALIDATION STEP 19 PENDING

## Purpose

This policy makes versions of Product artifacts explicit and prevents a release from silently
reinterpreting persisted Case, Result, Replay, Agent, Corpus, or Renderer data.

## Version format

Versioned Product schemas use `MAJOR.MINOR.PATCH`.

- `PATCH` is backward-compatible clarification or correction that does not change the schema contract.
- `MINOR` may add backward-compatible optional fields or capabilities.
- `MAJOR` represents an incompatible schema contract and requires an explicit migration path or a
  deliberate rejection of older/newer artifacts.

Agent versions, corpus versions, reasoning/renderer versions, and release versions remain separate.
Changing one does not silently change another.

## Reader compatibility

The canonical executable rule is `validation/schema_compatibility.py`.

A reader may directly consume an artifact when both use the same major schema version and the
artifact version is not newer than the reader. A newer same-major artifact returns
`MIGRATION_REQUIRED`; a major mismatch returns `INCOMPATIBLE` unless an explicit migration is
registered and executed.

No compatibility decision may be inferred from file names or prose labels alone.

## Migration contract

Every migration has:

- a unique migration id;
- an explicit artifact type;
- exact source and target schema versions;
- a declared reversibility property.

Duplicate migration edges are rejected. An absent migration is not treated as an identity
transformation.

## Rollback

Release rollback restores a previously validated Product revision and its compatible artifact set.
A rollback must not claim to reverse an irreversible data migration. Where a migration is not
reversible, the pre-migration artifact must remain available as immutable evidence or the release
must be blocked until a safe rollback strategy exists.

## Release evidence

Production Validation Step 19 requires evidence for:

1. versioning policy defined;
2. migration policy defined;
3. schema compatibility tested;
4. rollback policy defined.

This document and its tests establish the policy implementation, but Step 19 remains sequentially
pending until earlier Production Validation steps have passed and exact-step evidence is generated
on the validated release candidate revision.

## Non-goals

This policy does not itself certify a release, execute migrations, mutate private Case data, or
bypass the Production Validation Program. Step 20 remains the only Release Candidate decision gate.
