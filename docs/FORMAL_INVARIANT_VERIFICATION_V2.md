# FIV-02 — Bounded Critical Invariant Verification v2

Status: `CLOSED / ENGINEERING PASS`
Authority: verification-only derived control
Canonical Product history authority: Canonical Case Ledger (CCL)
Implementation baseline: `main @ 8ec20cc14ed43aa045f35b28796ed3a973c7f10a`
Validated implementation PR head: `a221a9d56d7134b7e23d769eb56027ba3f862063`
Implementation PR: `#176`
Implementation merge: `main @ 38540d95db212cfc2c80be54853202f77b41a45f`

## 1. Problem

IV-01 verifies a fixed six-check integration registry, but its primary evidence is point verification of supplied artifacts. FIV-02 strengthens the long-horizon regression boundary by exercising bounded deterministic state/property traces over trust-critical production contracts. It is not a claim of whole-system mathematical proof and does not introduce a solver, persistence authority or Product truth store.

## 2. Decision

FIV-02 uses a stdlib-only bounded trace verifier over synthetic isolated state. Semantic decisions remain delegated to existing production contracts. No external model checker or provider becomes a trust authority.

The fixed v2 registry covers exactly:

1. `APPEND_ONLY_EXACT_HEAD` — stale CCL heads are rejected and only the exact current head advances history.
2. `CONTENT_IDENTITY_DOMAIN_SEPARATION` — immutable revision identity is deterministic and binds both logical object identity and content.
3. `MIGRATION_PATH_DETERMINISM` — repeated explicit migration is identical; ambiguous and nondeterministic routes fail closed.
4. `AUTHORIZATION_ISOLATION` — tenant, case, permission and classification boundaries deny unauthorized access.
5. `REPLAY_PROJECTION_EQUIVALENCE` — repeated offline Case Replay v2 rebuild reproduces exact manifest-bound Epistemic and Trust Graph identities.
6. `RECOVERY_ATOMICITY` — an injected second-write failure during synthetic restore leaves no partial canonical history; exact retry restores the original bundle.

Changing the invariant set or budgets is a versioned contract change.

## 3. Bounded exploration and evidence

Each probe records a deterministic ordered trace. Every trace point binds an action, outcome and content-addressed state identity. Each trace, invariant result and final report is content-addressed. The final report additionally binds the exact candidate Git SHA and exact reference registry identity.

The hard trace budget is fixed in code. Exceeding it is failure, never truncation or partial PASS.

## 4. Safety and authority boundaries

FIV-02 MUST NOT:

- read or mutate private/real case data;
- append to a production CCL;
- change authorization, migration, replay or recovery semantics;
- publish releases or promote trust;
- use network/provider responses as invariant truth;
- turn any failed probe into partial PASS.

All writable state used by the verifier is synthetic and confined to an isolated scratch directory.

## 5. Alternatives considered

### External SMT/model checker

Rejected for v2. It would add toolchain/supply-chain lock-in and a new translation layer whose correctness would itself need verification. Current invariants are small and already have executable production contracts.

### Duplicate pure reference implementation

Rejected. A second implementation would become a competing semantic authority and could disagree with Product contracts.

### Bounded production-contract exploration

Selected. It minimizes new authority, keeps failure modes observable, is deterministic and provider-independent, and directly detects regressions in the contracts that actually execute in production.

## 6. Fail-closed semantics

Malformed or stale exact-SHA identity, registry drift, trace identity mismatch, stale-head acceptance, identity collapse, ambiguous/nondeterministic migration, authorization escape, replay divergence, partial restore or unexpected production exception aborts verification. No incomplete report can be interpreted as PASS.

## 7. Validation contract

FIV-02 is CLOSED only after:

- focused and adversarial FIV-02 tests PASS;
- IV-01 and recovery regression tests PASS;
- Ruff and MyPy PASS;
- repository security/policy workflows PASS;
- all exact-PR-head workflow runs are terminal SUCCESS on one unchanged candidate SHA;
- guarded exact-head merge succeeds;
- resulting `main` completes post-merge validation without failure or pending state;
- immutable `v1.0.1` tag/target remains unchanged and no unintended release is created;
- canonical roadmap/Master Plan closure evidence records exact SHAs.

## 8. Exact implementation evidence

The first implementation candidate failed repository lint only; the repair changed typing/formatting syntax without weakening a verifier, test, threshold or trust boundary. That earlier candidate is stale and is not closure evidence.

The final implementation candidate was `a221a9d56d7134b7e23d769eb56027ba3f862063`. All 13 PR-triggered workflows for that exact unchanged head completed `SUCCESS`, including the dedicated FIV-02 workflow, Stage Gate, Stage Orchestrator, CI Foundation, Enterprise Hardcore Gate, Enterprise CodeQL, GitHub App Smoke Test, Production Validation, P2/P3 compatibility and SSC-02 continuity.

PR #176 was guarded-merged with `expected_head_sha=a221a9d56d7134b7e23d769eb56027ba3f862063`. The resulting implementation merge is `main @ 38540d95db212cfc2c80be54853202f77b41a45f`.

Post-merge evaluation of that exact implementation merge observed 11 workflow runs after the release guard completed. Every run was terminal `SUCCESS`; there were no failed, cancelled or in-progress runs when implementation closure evidence was captured. The dedicated FIV-02 push validation succeeded on the exact merge SHA.

The immutable historical identity remained unchanged: annotated tag object `9f7c0b28f766c8921e63b1d517fefcc96aa991d4` still targets commit `802013c4d0e53dc12306a97e1877ebba86af64a7`. The latest release remained historical `v1.0.1`; FIV-02 did not publish a new release.

This is bounded engineering verification of executable trust-critical invariants. It is not independent external review, mathematical whole-system proof or formal-methods certification.

Independent external/formal certification is not implied by engineering closure.
