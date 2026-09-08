# DR-02 — Recovery Continuity & Backend Conformance v1

Status: IMPLEMENTATION / VALIDATION PENDING

## Problem

DR-01 already provides two correct recovery primitives:

1. `SQLiteProvenanceStore.restore_verified()` verifies complete backend `RecoveryIdentity` before atomically replacing a destination database.
2. `CanonicalCaseLedger.restore_case()` restores one verified `CaseLedgerBundle` into an empty case stream while preserving exact canonical event identities.

The remaining long-horizon risk is not a missing backup mechanism. It is loss of evidence that a recovery performed after a storage/runtime/environment change preserved the same Product history and used an explicitly identified storage profile.

## Decision

DR-02 adds a deterministic evidence layer over the existing recovery boundaries. It does not create a second backup format, a second database authority, or a competing case-history SSOT.

The contract consists of:

- `StorageProfileV1` — content-addressed identity of a storage implementation/profile using only non-secret configuration identity;
- `RecoveryDrillManifestV1` — immutable declaration binding source/target storage-profile identities, exact source `CaseLedgerBundle`, CCL head/event count and source backend `RecoveryIdentity`;
- `RecoveryConformanceReportV1` — content-addressed result binding the manifest to the actual restored bundle/head/event count and verified target backend identity;
- `run_sqlite_case_recovery_drill()` — a tested adapter that exercises the real `CanonicalCaseLedger.restore_case()` boundary for the only currently implemented durability backend.

## Trust boundary

- Canonical Case Ledger remains the only writable Product case-history authority.
- `CaseLedgerBundle` remains the canonical portable case-history artifact.
- `RecoveryIdentity` remains the durability-layer state identity.
- DR-02 manifests/reports are derived verification evidence only; `PASS` cannot promote facts, Gold, Product truth, release state or authorization.
- Backend record identities are intentionally allowed to differ after case-level restore; Product continuity is proven by exact CCL bundle/head identity, while each backend must independently verify its own durability identity.

## Fail-closed rules

DR-02 rejects or reports failure for:

- unknown/unsupported schema or serialized fields;
- invalid/tampered content digests;
- an undeclared backend adapter;
- target restore refusal, including a non-empty target case stream;
- case ID, bundle digest, head-event identity or event-count mismatch;
- malformed backend recovery identity.

A future backend does not become supported by merely naming it in `StorageProfileV1`; it requires a separate implementation adapter plus focused/adversarial conformance evidence.

## Determinism and measurement

Semantic recovery `PASS` is independent of wall-clock duration. RTO/RPO and performance measurements may be collected as operational evidence, but raw timing is intentionally excluded from the deterministic manifest/report identity because it is environment-dependent and must not change correctness semantics.

## Validation required for closure

- focused contract and round-trip tests;
- adversarial tamper/unknown-field/backend/refusal tests;
- exact Product bundle/head preservation through the real CCL restore path;
- full regression, Ruff, MyPy, security/policy gates;
- complete exact-head PR CI;
- unchanged-head/base guarded merge;
- resulting-main post-merge validation;
- immutable `v1.0.1` baseline/release check;
- governance closure sync and activation of `SSC-02` only after all evidence above is terminal PASS.
