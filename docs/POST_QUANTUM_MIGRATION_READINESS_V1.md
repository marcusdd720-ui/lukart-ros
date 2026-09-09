# LRD-01F — Post-Quantum Migration Readiness / Archival Trust Renewal v1

Status: `ACTIVE / IMPLEMENTATION CANDIDATE`
Parent program: `continuous LRD-01`
Depends on: `LRD-01E CLOSED / ENGINEERING PASS`
Measured base: `main @ 39ee52bdefdcff657abb900c7b4e53bffdefbf96`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01E proves additive classical renewal and current long-range health, but CRY-01 still
implements only Ed25519. A long-horizon system must know exactly where quantum-vulnerable
public-key signatures remain, preserve historical verification, and prepare a migration path
without pretending that naming a standardized post-quantum algorithm creates a supported
cryptographic implementation.

LRD-01F therefore closes **migration readiness**, not post-quantum deployment.

## 2. External standards evidence

The migration target registry references two finalized NIST post-quantum signature families:

- `ML-DSA` — `NIST-FIPS-204`;
- `SLH-DSA` — `NIST-FIPS-205`.

The registry is standards-identification evidence only. LRD-01F deliberately selects no
operational parameter set, implementation library, private-key format, HSM integration or
production cutover. Those require separately implemented and validated adapter evidence.

## 3. Existing authority reused

- CRY-01 (`core.crypto_agility_v1`) remains the sole crypto-agility/trust-set/key-lifecycle
  authority and remains `ED25519`-only.
- LRD-01E (`core.long_range_health_v1`) remains the current freshness/renewal/portability
  health authority.
- Canonical Case Ledger remains the sole writable case-history SSOT.
- Historical attestations and renewal evidence remain immutable. PQ migration is additive;
  historical bytes are never rewritten or silently re-signed.

## 4. Contract

`core.post_quantum_readiness_v1` adds four immutable/content-addressed derived artifacts:

1. `PqcTargetFamilyProfileV1`
   - fixed candidate families `ML-DSA` and `SLH-DSA`;
   - exact NIST standard identifier;
   - `adapter_required=true`;
   - `operational_parameter_set=null`.
2. `PqcMigrationPolicyV1`
   - fixed two-family registry cannot be caller-reduced;
   - original evidence must be preserved;
   - renewal must be additive;
   - dual verification is required before any future cutover.
3. `PqcReadinessReportV1`
   - derives the complete CRY-01 signature-key inventory from the exact trust set;
   - binds current LRD-01E health evidence and exact trust-set identity;
   - result is `ADAPTER_REQUIRED` only when current long-range health is `HEALTHY`;
   - otherwise result is `BLOCKED_CURRENT_HEALTH`;
   - `post_quantum_support` is structurally forced to `false` in v1.
4. `ArchivalRenewalPlanV1`
   - binds the readiness report, current classical crypto evidence and both target-family
     identities;
   - preserves original evidence and requires additive renewal plus dual verification;
   - can become `READY_FOR_ADAPTER_IMPLEMENTATION`, but never authorizes PQ execution.

## 5. Evidence -> alternatives -> trade-offs -> decision

### Alternative A — extend CRY-01 enum with ML-DSA immediately

Rejected. An enum entry without a verified signing/verifying adapter, parameter-set identity,
test-vector evidence, dependency provenance and key lifecycle implementation would manufacture
support that does not exist.

### Alternative B — choose one concrete PQ parameter set now

Rejected for 01F. It would introduce premature algorithm/library lock-in without measured
interoperability, performance, key-management and provider evidence.

### Alternative C — fixed standards-aware readiness registry + explicit adapter blocker

Selected. It makes current quantum exposure measurable now, preserves historical evidence,
keeps migration additive and creates a deterministic hand-off contract for a future adapter
stage without granting that future stage implicit trust.

## 6. Fail-closed rules

LRD-01F rejects:

- unknown schema or fields;
- a reduced/expanded/reinterpreted target registry;
- a target family bound to the wrong NIST standard;
- any claimed validated adapter or operational parameter set;
- any `post_quantum_support=true` claim;
- cross-case health/readiness substitution;
- readiness assessments older than their health evidence;
- readiness/health/policy digest substitution;
- altered plan/report digests;
- any archival plan that disables original-evidence preservation, additive renewal or
  pre-cutover dual verification;
- any attempt to authorize PQ execution from this contract.

## 7. Security / epistemic boundary

This slice does not:

- implement ML-DSA or SLH-DSA;
- store private keys;
- select a production parameter set;
- promote a trust root;
- mutate the Canonical Case Ledger;
- change Product/Gold/policy/release authority;
- claim post-quantum security, FIPS validation, independent cryptographic review or external
  certification.

A future adapter stage must bind exact implementation/library/version/build provenance,
parameter set, standard revision/errata identity, test vectors, key lifecycle, failure modes,
performance, interoperability and independent evidence before support can be claimed.

## 8. Validation scope

Focused/adversarial validation covers:

- exact two-family target registry;
- deterministic policy/report/plan identity;
- complete CRY-01 Ed25519 surface inventory;
- healthy versus stale/unverifiable health behavior;
- cross-case and stale-time rejection;
- unknown-field and digest tamper rejection;
- fake PQ support/adapter/parameter-set rejection;
- additive archival-renewal invariants;
- absence of signing and CCL write paths;
- CRY-01/LRD-01E/LRD-01D/escrow/replay regression.

## 9. Definition of Done

LRD-01F closes only after one exact candidate proves:

1. standards-aware fixed PQ candidate-family registry;
2. exact current CRY-01 signature-surface inventory;
3. explicit `ADAPTER_REQUIRED` / `BLOCKED_CURRENT_HEALTH` semantics;
4. no PQ implementation/support claim;
5. additive archival-renewal plan preserving original evidence;
6. focused and adversarial tests;
7. CRY-01/LRD-01E/replay/escrow/drift regression;
8. Ruff, strict MyPy, security/policy and full repository gates;
9. all exact PR-head CI terminal `SUCCESS`;
10. unchanged-head guarded merge;
11. resulting-main post-merge validation terminal `SUCCESS`;
12. immutable `v1.0.1` tag/target/release unchanged;
13. canonical closure evidence merged into GitHub.

## 10. Next boundary

LRD-01F does not authorize implementation of a PQ signing adapter. A later stage may be opened
only by explicit scope and must not inherit 01F engineering PASS as evidence that PQ cryptography
is implemented, interoperable or certified.
