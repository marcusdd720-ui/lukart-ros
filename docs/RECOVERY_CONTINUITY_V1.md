# DR-02 — Recovery Continuity & Backend Conformance v1

Status: CLOSED / ENGINEERING PASS

## Problem

DR-01 already provides two correct recovery primitives:

1. `SQLiteProvenanceStore.restore_verified()` verifies complete backend `RecoveryIdentity` before atomically replacing a destination database.
2. `CanonicalCaseLedger.restore_case()` restores one verified `CaseLedgerBundle` into an empty case stream while preserving exact canonical event identities.

The remaining long-horizon risk was not a missing backup mechanism. It was loss of evidence that a recovery performed after a storage/runtime/environment change preserved the same Product history and used an explicitly identified storage profile.

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

## Exact closure evidence

- implementation PR: `#172`;
- validated exact PR head: `498e8ac5ad788a2bd26f9ba2329f427e30e9c1e7`;
- exact-head PR CI: `11/11 SUCCESS`, including CI Foundation, Stage Gate, Enterprise Hardcore Gate and Enterprise CodeQL;
- guarded merge used unchanged head/base with `expected_head_sha=498e8ac5ad788a2bd26f9ba2329f427e30e9c1e7`;
- implementation merge: `main @ ed1e214a7a16897d7e1e8cb3dc719ebf9cf72e04`;
- implementation merge post-merge validation: `9/9 SUCCESS`, with zero queued or in-progress runs at closure evaluation;
- historical `v1.0.1` annotated tag object remained `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- historical `v1.0.1` target commit remained `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- no new release was published as a DR-02 side effect;
- no independent external/security/disaster-recovery certification is claimed.

## Closed controls

- exact source/target storage-profile identity is content-addressed without storing secret configuration;
- exact Product `CaseLedgerBundle`, CCL head and event count are bound into the recovery drill manifest;
- source and target durability identities are recorded independently from Product identity;
- real CCL restore semantics are exercised rather than emulated by a parallel recovery engine;
- non-empty target case streams remain fail-closed/no-overwrite;
- Product bundle/head mismatch becomes deterministic `FAIL` evidence;
- undeclared future backends fail closed until a separately implemented adapter passes the same conformance contract;
- deterministic semantic PASS is not coupled to nondeterministic wall-clock performance;
- no second Product SSOT, backup format, persistence authority, Gold authority, release authority or implicit trust promotion is introduced.

Next approved stage after canonical governance closure: `SSC-02`.
