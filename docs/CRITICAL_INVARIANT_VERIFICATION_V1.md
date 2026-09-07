# Critical Invariant Verification v1

Status: IV-01 implementation contract
Authority: verification-only derived control
Canonical Product history authority: Canonical Case Ledger (CCL)

## 1. Problem

LUKART ROS already enforces trust-critical contracts in separate production modules: CCL,
recovery, Case Replay v2, deterministic migrations, Epistemic v2 and Semantic Change v2.
The long-horizon risk is not absence of those controls but silent regression between them,
especially after future runtime, storage, schema or implementation changes.

IV-01 therefore verifies a deliberately small set of critical invariants. It does not try
to formally verify the whole product and does not create a second truth store.

## 2. Architectural decision

`core/critical_invariants.py` is a read-only orchestration layer. The verifier MUST delegate
semantic truth checks to existing production contracts rather than duplicate their logic.

Authority remains:

`Evidence -> CCL -> Epistemic -> Trust Graph -> Reasoning -> Result -> Replay`

IV-01 sits outside that authority chain as verification evidence only.

The module MUST NOT:

- instantiate or write a Canonical Case Ledger;
- append/publish/restore authoritative events;
- open SQLite or another persistence backend;
- reinterpret FACT, replay, migration or propagation semantics;
- turn a failed check into a partial PASS report.

## 3. Reference invariant registry

The v1 registry is exact, ordered and content-addressed. It contains exactly six checks:

1. `CCL_BUNDLE_INTEGRITY` — portable CCL history verifies its canonical chain and digest.
2. `RECOVERY_IDENTITY_EQUIVALENCE` — independently verified source/restored bundles are
   exactly identical.
3. `REPLAY_REBUILD_EQUIVALENCE` — Case Replay v2 rebuild reproduces manifest-bound
   Epistemic and Trust Graph identities.
4. `MIGRATION_DETERMINISM` — the explicit migration path reproduces the same immutable
   target and path identity on repeated execution.
5. `EPISTEMIC_REBUILD_EQUIVALENCE` — the exact case history and policy reproduce the same
   Epistemic projection identity.
6. `SEMANTIC_PROPAGATION_BOUNDED` — repeated propagation produces the same replay-bound
   plan and never exceeds node/depth/work policy budgets.

Changing this set is a versioned contract change. A caller cannot substitute a smaller
registry and still obtain an IV-01 PASS report.

## 4. Exact-SHA binding

`verify_critical_invariants()` requires both `code_sha` and `expected_code_sha`.
Verification fails before any invariant runs unless both identifiers are canonical Git
object IDs and exactly equal.

The expected SHA comes from the external execution boundary, e.g. the exact PR-head SHA
being validated by CI. The verifier does not infer Git state and therefore cannot silently
verify a different checkout.

The final report content identity binds:

- exact code SHA;
- exact reference registry identity;
- every required invariant result identity;
- every result evidence identity;
- report schema and PASS outcome.

A different exact code SHA necessarily produces a different report identity.

## 5. Fail-closed semantics

There is no partial-success report. Any malformed input, content-address mismatch, replay
mismatch, migration ambiguity/nondeterminism, cross-case Epistemic substitution, semantic
budget overflow, stale exact-SHA binding or unexpected production-contract exception aborts
verification.

Only a complete run of all reference checks can construct a `PASS` report.

## 6. Production-contract reuse

IV-01 delegates to:

- `CanonicalCaseLedger.verify_export()` for portable CCL verification;
- `verify_case_replay_bundle()` for offline replay reconstruction;
- `CaseMigrationRegistry.migrate()` for explicit path and deterministic migration checks;
- `EpistemicProjectionV2.build()/verify()` for epistemic rebuild;
- `SemanticChangeGraphV2.plan()` and plan verification for bounded propagation.

Recovery equivalence verifies both sides through the CCL export contract before comparing
canonical bundle identity. Atomic write/rollback behavior remains the responsibility of
DR-01's production restore path and its dedicated adversarial tests.

## 7. Adversarial and state validation

The IV-01 suite covers at least:

- exact registry completeness and deterministic identity;
- deterministic complete report generation;
- exact-SHA mismatch and malformed Git identity rejection;
- tampered CCL and replay artifacts;
- two valid but non-identical recovery histories;
- nondeterministic migration function;
- cross-case epistemic rebuild substitution;
- semantic blast-radius overflow with hard failure;
- repeated CCL state transitions with stale-head rejection after every accepted write;
- recovery refusal against a non-empty target stream;
- static assertion that the IV-01 verifier has no CCL write or SQLite authority.

These tests are intentionally bounded model/state checks over small trust-critical
contracts. They are not a claim of whole-system formal verification.

## 8. Evidence and closure

IV-01 reaches `CLOSED / ENGINEERING PASS` only after:

- focused and adversarial tests pass;
- full regression/lint/type/security/policy checks pass;
- all required exact-SHA PR workflows pass on one unchanged candidate SHA;
- guarded exact-head merge succeeds;
- resulting `main` completes post-merge validation without unresolved failure/pending state;
- historical immutable release identity remains unchanged.

Independent external certification is not implied by engineering closure.