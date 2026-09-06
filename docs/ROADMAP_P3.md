# LUKART ROS — P3 Production Integration

P3 starts from the merged P2 baseline `62e959f93f4930c921429d1243e3f21772bba661`.
It does not reopen the v1.0.1 release, historical RC, or locked evaluation data.

## Operating standard

P3 uses contract-first, adversarial-first, deterministic, measurable, reversible,
provenance-aware and fail-closed engineering. New orchestration must integrate the
existing P2 authorities rather than create a second reasoning or semantic authority.

## Hardening Gate

Before P3 is considered integrated, CI must exercise negative paths for integrity,
provenance tampering, partial persistence, migration non-determinism, trust-state
bypass, provider failure, timeout/cancellation, API tampering and plugin permissions.
Full repository regression remains mandatory.

## P3-01 — Semantic Change Graph

- Project Reasoning support/evidence lineage into explicit dependencies.
- Reuse P2 `semantic_diff`; do not fork semantic comparison authority.
- Produce deterministic affected sets and shortest reason paths.
- Reject unknown change roots and dependency cycles fail-closed.

## P3-02 — Persistent Replay & Provenance Store

- Canonical JSONL records.
- SHA-256 payload binding and record hash chain.
- Runtime identity binding.
- Detect truncation, tampering and sequence discontinuity.
- Current local backend is a single-writer contract for multi-process deployments.

## P3-03 — Case Versioning & Migration Registry

- Explicit migration routes only.
- Source case remains immutable.
- Migration path replays twice and must produce the same digest.
- Semantic diff remains visible after migration.
- Same-version migration is idempotent.

## P3-04 — Explainability / Dossier Integration

- Dossier binds to exact Reasoning digest.
- Preserves support lineage, evidence, open questions and counterfactual checks.
- Carries explicit contradictions without inventing a new reasoning authority.

## P3-05 — Longitudinal Quality Intelligence

- Metrics have explicit `HIGHER_IS_BETTER` / `LOWER_IS_BETTER` objectives.
- Release SHA and corpus digest are part of each observation.
- Missing metrics remain visible rather than silently passing.

## P3-06 — Controlled Experiment Manager

Lifecycle:

`FAILURE -> CANDIDATE -> EXPERIMENT -> VALIDATION -> PROMOTION -> MONITORING`

Rollback remains explicit. Promotion requires a validation digest and approver;
trusted status is reached only after promotion enters monitoring.

## P3-07 — Agent Runtime Production Hardening

- certified-provider allow-list
- deterministic fallback
- provider health
- timeout and cancellation controls
- concurrency and existing P2 step budgets
- immutable audit records

The current boundary is thread/logical isolation. It is **not** an OS/process sandbox.

## P3-08 — Stable LUKART API v1

Official resource families:

`Case`, `Evidence`, `Fact`, `Reasoning`, `Result`, `Replay`, `KQM`, `Explainability`.

API resources use the existing P2 digest envelope plus P3 inner-payload and runtime-
identity digests. Unknown schema/version pairs fail closed.

## P3-09 — Realistic Performance & Scale Certification

Synthetic profiles measure runtime, peak memory, cache effectiveness, bounded
parallel replay and deterministic work digests. Shared CI runner timing is engineering
evidence only and must not be represented as analytical certification.

## P3-10 — Plugin SDK & Isolation Boundary

Plugins are class-based and bound to immutable manifests. Capability, identity, API
version, permissions and dependency declarations must match host policy. The P3
boundary is logical/manifest isolation and explicitly does not claim OS sandboxing.

## P3 completion gate

P3 engineering integration requires:

1. focused P3 lint and type checks,
2. P3 adversarial suite,
3. complete repository regression,
4. policy integrity checks,
5. all applicable repository PR workflows passing,
6. merge only after the above.

Engineering PASS is not an independent analytical certification or Gold freeze.
