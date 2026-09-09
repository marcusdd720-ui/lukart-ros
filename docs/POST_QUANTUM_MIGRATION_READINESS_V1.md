# LRD-01F — Post-Quantum Migration Readiness / Archival Trust Renewal v1

Status: `CLOSED / ENGINEERING PASS` closure candidate; authoritative after guarded closure merge
Parent program: `continuous LRD-01`
Depends on: `LRD-01E CLOSED / ENGINEERING PASS`
Measured base: `main @ 39ee52bdefdcff657abb900c7b4e53bffdefbf96`
Implementation PR: `#201`
Validated implementation head: `f9c550c31dc77d2402ad1931fbacfc821763ac80`
Implementation merge: `main @ 46080d4d9ddc3f1df3a358cccad658d36bc41bff`
Implementation PR CI: `19/19 SUCCESS`
Implementation post-merge: `18/18 SUCCESS`, `queued=0`, `in_progress=0`, `failure=0`
Historical baseline tag object: `v1.0.1 @ 9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
Historical baseline target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
Latest release at implementation closure: `v1.0.1` / `MVROS 1.0.1`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01E proves additive classical renewal and current long-range health, but CRY-01 still
implements only Ed25519. A long-horizon system must know exactly where quantum-vulnerable
public-key signatures remain, preserve historical verification, and prepare a migration path
without pretending that naming a standardized post-quantum algorithm creates a supported
cryptographic implementation.

LRD-01F closes **migration readiness**, not post-quantum deployment.

## 2. Standards identity

The fixed migration target registry references two finalized NIST post-quantum signature
families:

- `ML-DSA` — `NIST-FIPS-204`;
- `SLH-DSA` — `NIST-FIPS-205`.

These identifiers are standards-target evidence only. LRD-01F deliberately selects no
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

## 4. Implemented contract

`core.post_quantum_readiness_v1` adds immutable/content-addressed derived evidence:

1. `PqcTargetFamilyProfileV1`
   - fixed `ML-DSA` and `SLH-DSA` candidate families;
   - exact NIST standard identifier;
   - `adapter_required=true`;
   - `operational_parameter_set=null`.
2. `PqcMigrationPolicyV1`
   - the two-family registry cannot be caller-reduced, expanded or reinterpreted;
   - original evidence must be preserved;
   - renewal is additive only;
   - dual verification is mandatory before any future cutover.
3. `PqcReadinessReportV1`
   - inventories the complete current CRY-01 signature-key surface from the exact trust set;
   - binds current LRD-01E health and exact trust-set identity;
   - returns `ADAPTER_REQUIRED` only when current long-range health is `HEALTHY`;
   - otherwise returns `BLOCKED_CURRENT_HEALTH`;
   - structurally forces `post_quantum_support=false`.
4. `ArchivalRenewalPlanV1`
   - binds readiness, current classical crypto evidence and both target-family identities;
   - preserves original evidence and dual-verification requirements;
   - may become `READY_FOR_ADAPTER_IMPLEMENTATION` but never authorizes PQ execution.

## 5. Evidence -> alternatives -> trade-offs -> decision

### Alternative A — extend CRY-01 with PQ algorithm names immediately

Rejected. An enum value without an exact signing/verifying adapter, parameter-set identity,
test-vector evidence, dependency provenance and key lifecycle implementation would manufacture
support that does not exist.

### Alternative B — choose one operational PQ parameter set now

Rejected for 01F. It would create premature algorithm/library lock-in without measured
interoperability, performance, key-management and provider evidence.

### Alternative C — standards-aware readiness registry + explicit adapter blocker

Selected. It makes current quantum exposure measurable, preserves historical evidence and
creates a deterministic hand-off contract for a later adapter stage without granting that
future stage implicit trust.

## 6. Fail-closed and adversarial evidence

LRD-01F rejects:

- unknown schema or fields;
- reduced/expanded/reinterpreted target registry;
- wrong standard/family binding;
- claimed validated adapter or operational parameter set;
- `post_quantum_support=true`;
- cross-case health/readiness substitution;
- readiness assessment predating current health evidence;
- readiness/health/policy digest substitution;
- altered plan/report digests;
- disabling original-evidence preservation, additive renewal or dual verification;
- any attempt to authorize PQ execution from 01F.

Focused/adversarial tests also prove deterministic target/policy/report/plan identities,
complete CRY-01 Ed25519 surface inventory, healthy versus stale/unverifiable behavior and the
absence of signing or Canonical Case Ledger write paths. Regression covers CRY-01, LRD-01E,
LRD-01D, escrow and replay.

## 7. Repair history

The initial implementation candidate `058d6be2b6a174f29e8cc5f94e109cbaf5809c02`
failed before semantic tests because Ruff reported seven `UP037` findings for quoted return
annotations while `from __future__ import annotations` was active. No architecture, runtime,
security, test-threshold or trust-boundary defect was found.

The smallest justified repair removed only those redundant annotation quotes. It produced fresh
candidate `f9c550c31dc77d2402ad1931fbacfc821763ac80`; all evidence from the prior candidate became
stale. The fresh candidate then passed all 19 PR workflows, including the dedicated LRD-01F
workflow, Stage Gate, CI Foundation, Enterprise Hardcore, Enterprise CodeQL and the existing
long-range/recovery/supply-chain gates.

## 8. Merge and implementation post-merge evidence

PR #201 was mergeable with unchanged head
`f9c550c31dc77d2402ad1931fbacfc821763ac80` and unchanged base
`39ee52bdefdcff657abb900c7b4e53bffdefbf96`. Guarded merge used the expected exact head and
produced implementation main `46080d4d9ddc3f1df3a358cccad658d36bc41bff`.

The exact implementation main completed 18 recorded post-merge workflow runs, all terminal
`SUCCESS`, with zero failed, queued or in-progress runs at closure evaluation. This included the
dedicated LRD-01F validation, Stage Gate, Enterprise CodeQL, Enterprise Hardcore, long-range
regression, governance closure preparation and the release guard.

Governance closure preparation itself created no LRD-01F closure PR because this new slice was
not configured as an automation target. No gate was bypassed: canonical closure is therefore
recorded through the controller-side closure path used for unsupported selectors.

## 9. Historical baseline and non-claims

At implementation closure:

- `v1.0.1` still resolves to annotated tag object
  `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- that tag object still targets
  `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- latest published release remains `v1.0.1` / `MVROS 1.0.1` targeting that same commit;
- no release or tag was created or moved.

LRD-01F does **not** implement ML-DSA or SLH-DSA, store private keys, select a production
parameter set, promote trust roots, mutate CCL, change Product/Gold/policy/release authority or
claim post-quantum security, FIPS validation, independent cryptographic review or external
certification.

A future PQ adapter must separately bind exact implementation/library/version/build provenance,
parameter set, applicable standard revision/errata identity, test vectors, key lifecycle,
failure modes, performance, interoperability and required independent evidence.

## 10. Definition of Done

LRD-01F closes only after this exact closure candidate itself proves:

1. fixed standards-aware PQ migration target registry;
2. exact current CRY-01 signature-surface inventory;
3. explicit `ADAPTER_REQUIRED` / `BLOCKED_CURRENT_HEALTH` semantics;
4. no fabricated PQ implementation/support claim;
5. additive archival-renewal plan preserving original evidence;
6. focused/adversarial/regression validation;
7. Ruff, strict MyPy, security/policy and full repository gates;
8. implementation exact-head `19/19 SUCCESS`;
9. guarded implementation merge and implementation-main `18/18 SUCCESS`;
10. immutable `v1.0.1` tag/target/release baseline unchanged;
11. fresh exact-head CI for this closure candidate;
12. guarded closure merge;
13. resulting-main post-merge validation terminal `SUCCESS`;
14. final baseline/release re-verification.

## 11. Next boundary

LRD-01F does not authorize implementation of a PQ signing adapter. A later stage requires
explicit scope and must not inherit 01F ENGINEERING PASS as evidence that PQ cryptography is
implemented, interoperable, production-ready or certified.
