# LRD-01A — Replay Closure Coverage & Architecture v1

Status: LRD-01A engineering architecture contract
Parent program: `continuous LRD-01`
Measured baseline: `main @ a884073591295af106baf1d6d87cf178830db315`
Writable case-history SSOT: Canonical Case Ledger (CCL) only
Machine-readable measurement: `evidence/lrd_01a/replay_closure_coverage_v1.json`

## 1. Problem

Periodic replay is not the same as long-range execution closure. A historical result can
remain logically identified while becoming impossible to verify after source hosting,
package registries, Python runtimes, providers/models, cryptographic profiles, storage
backends or exact execution inputs disappear.

LRD-01 therefore needs a 10+ year architecture that can distinguish what is actually bound,
preserved, regeneratable or unavailable. Missing identity or preservation evidence must
become an explicit `FAIL`, `UNKNOWN`, `UNVERIFIABLE` or `ABSTAIN`, never an inferred PASS.

LRD-01A closes the measurement and architecture prerequisite. It does **not** claim that the
full Long-Range Replay capability, external ten-year escrow or Frozen/Current execution
runner is already implemented.

## 2. Evidence inherited from the existing trust chain

LRD-01A extends existing contracts instead of replacing them:

- `CANONICAL_CASE_LEDGER_V1` — sole writable Product case-history authority, canonical event
  and bundle identity, explicit schema/canonicalization/digest identities and offline bundle
  verification;
- `CASE_REPLAY_V2` — exact case/replay identity over CCL, Epistemic v2, Evidence Trust Graph,
  RuntimeIdentity, schema identities and migration-registry identity;
- `AUTHORIZATION_POLICY_IDENTITY_V1` — content-addressed authorization semantics and exact
  policy reconstruction;
- `CRYPTO_AGILITY_V1` — explicit algorithm/trust-set identity, key lifecycle and verification
  receipts;
- `RECOVERY_CONTINUITY_V1` — content-addressed storage profiles and identity-preserving
  recovery conformance;
- `SIGNED_CASE_EXCHANGE_V2` — portable offline authorization re-verification over signed case
  exchange;
- `SUPPLY_CHAIN_CONTINUITY_V2` — exact source archive, lock/build identity, physical wheelhouse
  and standalone offline verifier.

The important measured limit is explicit: SSC-02 does not claim that GitHub Actions artifacts
or any current external location provide ten-year archival durability. LRD must preserve that
UNKNOWN/UNAVAILABLE boundary until separately evidenced infrastructure exists.

## 3. Replay Closure Coverage Matrix gate

Phase 0 is represented by the strict
`lukart.replay-closure-coverage.v1` machine-readable matrix. Each required trust-critical
item carries one or more orthogonal classifications:

- `BOUND` — an exact identity is already bound by an implemented contract;
- `UNBOUND` — a materially relevant identity/artifact is not yet bound by the LRD closure;
- `EXTERNAL` — the dependency exists outside LUKART authority;
- `PRESERVED` — exact physical/canonical material is already preserved by an implemented
  repository contract;
- `REGENERATABLE` — deterministic reconstruction is supported from bound material;
- `UNAVAILABLE` — required long-range capability/material is not currently available.

The design gate is deliberately different from capability PASS. The gate passes only when
**100% of the fixed trust-critical inventory is explicitly classified**. A classified
`UNBOUND`, `EXTERNAL` or `UNAVAILABLE` item remains a measured gap and is never promoted to a
positive preservation claim.

LRD-01A fixes 30 required items, including every item mandated by the program brief: code
SHA/tree, config, schemas, canonicalization profiles, migration chains, authorization/policy
identity, epistemic/trust policies, evidence/input digests, dependencies, wheels/sdists,
lockfiles, SBOM, Python/runtime/environment, storage identity, crypto profiles, verification
material, plugins, providers/models, exact requests, exact external responses, renderer
identity and semantic result identity. It additionally classifies source archive, offline
verifier, escrow backend/durability, crypto renewal, supersession lineage, offline-network
boundary and tenant/case isolation.

The matrix has a deterministic `sha256:` content identity derived from canonical JSON. A
material measurement change creates a different matrix identity.

## 4. Material gaps exposed by Phase 0

The matrix deliberately records, rather than hides, the following long-range gaps:

1. no independently evidenced ten-year immutable artifact-escrow backend or durability SLA;
2. generic exact configuration bytes are not yet preserved by Replay v2;
3. arbitrary evidence/input bytes are not universally escrowed even when their digests are
   bound;
4. exact external/provider requests and responses are not a generic preserved replay
   contract;
5. exact plugin executable material is not universally escrowed;
6. provider/model services remain external and may no longer exist;
7. Python/runtime/platform identity is declared, but an exact executable interpreter/runtime
   artifact is not generically preserved;
8. a dedicated renderer identity and canonical final semantic-result identity are not yet an
   LRD closure contract;
9. a generic immutable crypto-renewal attestation format is not yet implemented;
10. a least-privilege LRD runner with enforced network-off semantics is not yet implemented.

These are implementation targets for later LRD slices, not reasons to weaken the coverage
matrix or pretend present capability.

## 5. Alternatives

### A. Expand `CaseReplayManifestV2` in place

**Advantages:** fewer artifact types and short implementation path.

**Rejected:** it would retroactively broaden the meaning of a historical PHX-05 artifact,
mix case-replay identity with physical continuity/escrow/crypto-renewal concerns and make
older v2 records appear to carry execution-closure guarantees they never had.

### B. Versioned long-range envelope over existing replay — selected

Create a separately versioned `LongRangeReplayManifestV1` that references, rather than
redefines, exact existing identities such as Case Replay v2, supply-chain continuity,
authorization policy, crypto verification and storage/recovery evidence.

**Advantages:** preserves historical semantics, keeps components replaceable, provides a
clear migration boundary and permits missing components to fail closed without changing CCL
or Replay v2 authority.

**Trade-off:** one additional immutable manifest/capsule layer must be verified.

### C. Second replay/event database

**Rejected:** creates a competing writable history authority, synchronization failure modes
and a direct violation of the CCL single-SSOT invariant.

### D. VM/container snapshot as the replay authority

**Rejected as primary authority:** useful as preserved runtime material, but opaque snapshots
alone do not provide canonical semantic identity, policy/migration provenance, long-term
crypto renewal or provider independence. Runtime images may be referenced as artifacts but
cannot replace the manifest trust chain.

## 6. Selected architecture

Canonical long-range chain:

`Evidence -> CCL -> Case Replay v2 -> LongRangeReplayManifestV1 -> Replay Capsule V1`

`-> Frozen Path verification / Current Path comparison -> immutable replay evidence`

Everything after CCL is immutable input or derived verification evidence. None of the LRD
artifacts gains a Product write API, Gold mutation authority, policy-promotion authority,
trust-promotion authority or release authority.

### 6.1 `LongRangeReplayManifestV1`

The next implementation slice should bind at least:

- exact Case Replay v2 bundle/manifest identity;
- exact code SHA/tree and preserved source-archive identity;
- exact replay-relevant configuration artifact identities;
- complete schema and canonicalization-profile identities;
- exact migration-registry topology plus implementation/code identity;
- exact authorization, epistemic and trust-policy identities/snapshots;
- evidence/input artifact digests and preservation references;
- lockfiles, dependency artifacts, wheel/sdist/direct-source artifacts and SBOM identity;
- exact Python/runtime/platform/reconstruction identity;
- storage-profile identity without making a storage backend authoritative;
- crypto algorithm/profile/trust-set/verification-material identity;
- plugin identity plus executable/capability artifact identity when semantically material;
- provider/model identity plus exact request/response artifact identity when external
  execution affects semantics;
- semantic-result identity independent from renderer/presentation identity;
- optional renderer/presentation identity;
- exact artifact inventory and content addresses;
- optional `supersedes_digest` for immutable correction lineage;
- manifest schema/canonicalization/digest profile identity.

Unknown schema, canonicalization profile, migration route, policy identity, dependency
artifact, evidence digest, crypto profile, authorization or provider/plugin capability must
fail closed. No implicit compatibility fallback is permitted.

### 6.2 Replay Capsule V1

A published capsule is immutable and content-addressed. Corrections are represented only as:

`new capsule -> supersedes_digest -> old capsule`

The old capsule remains audit-accessible. The same rule applies to replay reports, migration
attestations, policy history and crypto-renewal evidence.

The capsule is a portable verification/evidence artifact, never a second case-history store.

### 6.3 Content-addressed Artifact Escrow

The escrow interface must be backend-neutral. Filesystem, object storage or a future backend
may hold bytes, but backend location is never artifact identity or Product authority.

Required properties:

- content-addressed artifact identity independent of backend location;
- exact byte-size and digest verification on read/restore;
- immutable publication semantics;
- backend migration preserving canonical artifact identity;
- no silent filename-based equivalence;
- archive path traversal, symlink escape and decompression-bomb resistance;
- bounded artifact/archive sizes and work.

Actual ten-year durability requires separate operational evidence from independent durable
locations. Repository CI cannot manufacture that claim.

## 7. Frozen Path and Current Path

### Frozen Path

Purpose: verify what happened historically using the exact historical closure material.

Properties:

- offline by default;
- read-only CCL/case/evidence/capsule inputs;
- preserved source, dependencies, runtime and external outputs when required;
- no live provider/model dependency where a preserved external response is the historical
  downstream input;
- network access during declared offline execution is a deterministic failure;
- missing identity/material becomes `UNVERIFIABLE` or `ABSTAIN`, never guessed replay.

### Current Path

Purpose: execute the same historical case through the currently supported stack and compare
canonical semantic identity with Frozen Path history.

Current Path produces a **new** runtime/result identity. It must never overwrite or reclassify
historical Frozen Path evidence.

Presentation-only differences do not constitute semantic regression. A true canonical
semantic mismatch must be reported separately from renderer/presentation drift.

## 8. Replay assurance levels

The later runtime contract must expose at least:

- `EXACT` — complete exact identity plus deterministic reconstruction of deterministic stages;
- `SEMANTIC` — canonical semantic identity is equal even though non-semantic execution or
  presentation identity differs;
- `VERIFIED_EXTERNAL` — historical external/provider output is verified as the exact preserved
  artifact and reused as downstream replay input; this does not claim deterministic provider
  rerun;
- `UNVERIFIABLE / ABSTAIN` — required identity/material is missing, unsupported or external
  execution cannot be established.

Bit-for-bit replay must never be claimed for a nondeterministic external provider/model merely
because its historical output was preserved.

## 9. Cryptographic survivability

Historical artifact identities are never rewritten to adopt a new algorithm.

Renewal model:

`original artifact/root digest -> renewal attestation -> new supported crypto profile`

A renewal attestation extends verifiability; it does not mutate the original historical
identity or automatically promote a new trust root. Unknown/downgraded algorithms, missing
verification material or unsupported profiles fail closed.

## 10. Least-privilege LRD runner boundary

The future LRD runner must have:

- read-only case/evidence/capsule access;
- zero CCL write authority;
- zero Gold mutation authority;
- zero policy/trust promotion authority;
- zero Product mutation authority;
- network OFF in declared offline mode;
- ephemeral workspace;
- explicit CPU, memory, elapsed-time, artifact-size, archive-expansion and concurrency bounds;
- short-lived minimal credentials only when an explicitly online operation requires them;
- exact tenant/case scope and cross-case substitution rejection.

## 11. Adversarial acceptance model for later implementation slices

The complete LRD capability must include at least these negative cases:

- one-byte artifact mutation;
- missing dependency;
- same filename with different digest;
- unknown schema;
- missing or ambiguous migration;
- policy substitution;
- provider-response substitution;
- crypto downgrade or unknown profile;
- unknown canonicalization profile;
- tenant/case mixing;
- locale/timezone/order/nondeterminism variation;
- alternate-storage restore;
- archive path traversal;
- symlink escape;
- decompression bomb;
- offline network attempt;
- renderer-only difference;
- true semantic mismatch.

LRD-01A itself validates the coverage contract adversarially: missing required items, unknown
classifications, unknown fields, invalid baseline SHA and non-canonical ordering fail closed;
a material matrix mutation changes its content identity.

## 12. Continuous LRD health

`LRD-01 Capability Baseline` and ongoing operational health are separate concepts.

A future baseline may close `CLOSED / ENGINEERING PASS` only after its complete Definition of
Done. Operational evidence later ages independently and should report states such as
`HEALTHY`, `DEGRADED`, `FAIL` or `UNKNOWN / STALE_EVIDENCE` according to measured evidence.

A historical PASS is not perpetual current-health evidence. Replay/restore cadence must be
justified by measured risk and recovery evidence rather than an arbitrary unmeasured SLO.

## 13. LRD-01A closure boundary

LRD-01A is complete only when one exact candidate SHA proves:

1. strict machine-readable coverage schema and fail-closed parser;
2. 100% classification of the fixed 30-item trust-critical inventory;
3. deterministic matrix content identity;
4. explicit retention of measured `UNBOUND`, `EXTERNAL` and `UNAVAILABLE` gaps;
5. focused and adversarial tests;
6. Ruff, strict MyPy and full pytest regression;
7. repository security/policy and exact-SHA CI PASS;
8. guarded unchanged-head merge;
9. resulting-main post-merge validation;
10. immutable `v1.0.1` tag/target/release baseline unchanged.

LRD-01A engineering PASS does not imply external ten-year storage durability, independent
security review, cryptographic certification or completion of the full LRD-01 capability.

## 14. Ordered continuation after LRD-01A

The best-justified implementation sequence is:

1. **LRD-01B — LongRangeReplayManifestV1 / Replay Capsule V1**: bind exact existing identities,
   assurance semantics, semantic-vs-presentation identity and immutable supersession;
2. **LRD-01C — Artifact Escrow / offline runner**: backend-neutral content-addressed escrow,
   bounded archive handling, physical runtime/config/plugin/external-output preservation and
   network-off least-privilege execution;
3. **LRD-01D — Frozen Path / Current Path / drift evidence**: deterministic frozen replay,
   current-stack comparison, semantic drift detection and explicit external verification;
4. **LRD-01E — crypto renewal / operational health**: renewal attestations, storage portability
   drills and freshness-aware long-range health evidence.

Each slice requires its own fresh exact-SHA validation and may not inherit PASS evidence from
LRD-01A.
