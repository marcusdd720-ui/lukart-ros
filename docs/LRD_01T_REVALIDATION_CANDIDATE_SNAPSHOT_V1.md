# LRD-01T — Revalidation Candidate Snapshot v1

Status: **CLOSED / ENGINEERING PASS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ 27b7416924548d947140920dc2d347dcc4c648f6`

This document is a stage contract/evidence map only. The sole engineering-process authority remains `docs/WORKING_PRINCIPLES.md`.

## Problem and measured gap

LRD-01S closes the bounded operational handoff from an already-selected baseline through LRD-01M→N→P→Q→R, but intentionally requires the caller to supply three candidate inputs: an exact candidate repository SHA, a complete candidate `RuntimeIdentity`, and the matching LRD-01M `ReplayRevalidationFingerprintV1`.

Fresh SSOT measurement after LRD-01S found no existing API that materializes those three inputs as one bounded candidate snapshot. Existing owners remain deliberately separate:

- `RuntimeIdentity` v3 owns complete execution identity and fails closed on undeclared inventories;
- LRD-01I owns the preserved offline survivability-bundle identity;
- SSC-02 owns supply-chain continuity identity;
- LRD-01K owns cross-environment profile, replay-policy, migration, canonicalization and crypto bindings;
- `CaseMigrationRegistry.digest()` owns deterministic migration-registry identity;
- DR-02 owns content-addressed `StorageProfileV1.profile_digest` identities;
- LRD-01G consumes DR-02 storage identities for multi-location escrow evidence;
- LRD-01H can derive a provider-specific storage profile without becoming Product/CCL/replay authority;
- LRD-01M builds and compares the dependency fingerprint but requires all current identities as explicit inputs;
- LRD-01S consumes candidate inputs but explicitly does not discover them or execute replay.

No existing component found in the measured implementation set composes a complete candidate RuntimeIdentity plus the corresponding LRD-01M fingerprint while binding both to one exact repository SHA. This is the bounded gap closed by LRD-01T.

## Selected design

LRD-01T introduces one deterministic, caller-triggered composition only:

`explicit runtime material + exact repository SHA + exact upstream identities → RuntimeIdentity v3 → LRD-01M fingerprint → content-addressed candidate snapshot`

`ReplayRevalidationRuntimeMaterialV1` carries all RuntimeIdentity v3 fields except `code_sha`. The candidate repository SHA is therefore the single source of code identity; a caller cannot submit one repository SHA and a different runtime code SHA into the same materialization call.

All provider/plugin/input/evidence inventories are explicit, including valid empty inventories. Materialization marks them declared and requires a complete v3 execution environment identity. The resulting `RuntimeIdentity` must be replay-complete.

`ReplayRevalidationCandidateSnapshotV1` binds:

- exact lowercase 40-character candidate repository SHA;
- canonical runtime material;
- the deterministically materialized `RuntimeIdentity`;
- the existing `ReplayRevalidationFingerprintV1` built from that exact runtime identity and the caller-supplied exact upstream content identities;
- a content-addressed `snapshot_digest` over the whole bounded candidate body.

The snapshot exposes the exact fingerprint, RuntimeIdentity and repository SHA consumed by LRD-01S. It does not call LRD-01S and does not persist or select a baseline.

## Upstream identity boundary

LRD-01T does not replace verification performed by upstream owners and does not manufacture external evidence. The caller supplies exact identities already derived from the authoritative contracts. LRD-01T validates their canonical form through the existing LRD-01M fingerprint builder and binds them together; it does not reread cloud state, storage, GitHub, the filesystem, dependency indexes or provider APIs.

The following remain upstream authorities rather than 01T authorities:

- LRD-01I bundle construction/verification;
- SSC-02 continuity manifest construction/verification;
- LRD-01K environment/replay-plan evidence;
- migration-registry implementation and digest;
- canonicalization/crypto profile ownership;
- DR-02/LRD-01G/LRD-01H storage-profile evidence;
- LRD-01S operational lineage persistence.

## Fail-closed semantics

Materialization rejects or cannot produce a valid snapshot when:

- the repository identity is a branch/ref such as `main`, malformed, uppercase, padded, truncated or not an exact 40-character Git SHA;
- runtime execution identity is incomplete;
- required environment-profile or storage-profile inventories are incomplete;
- any LRD-01M upstream digest is malformed;
- a fingerprint is substituted against a different materialized RuntimeIdentity;
- serialized RuntimeIdentity bytes do not match the exact RuntimeIdentity derivable from runtime material plus repository SHA;
- the snapshot digest is tampered;
- unknown fields or non-canonical serialized forms are introduced;
- any forbidden authority flag is injected as true.

A change in any bound upstream identity changes the LRD-01M fingerprint and the candidate snapshot identity.

## Authority boundary

LRD-01T is deterministic candidate composition only. It has no:

- repository watcher or change-detection authority;
- scheduler/cron authority;
- replay execution or runner orchestration authority;
- provider/cloud access authority;
- storage write/read authority;
- mutable latest/current pointer authority;
- Product write authority;
- Canonical Case Ledger write authority;
- release/tag/publication authority;
- baseline-selection persistence authority;
- policy/trust-root promotion authority;
- independent/human/security certification authority.

The dedicated CI workflow has `contents: read`, no `schedule:` trigger and checks that the implementation does not introduce provider/network/subprocess orchestration markers.

## Validation contract

Focused and adversarial validation covers:

- deterministic RuntimeIdentity v3 materialization from one exact repository SHA;
- complete declared inventories and execution environment;
- exact fingerprint binding to the materialized RuntimeIdentity;
- deterministic content-addressed snapshot identity;
- strict canonical round trip;
- mutable/non-canonical repository-ref rejection;
- incomplete runtime/environment/storage evidence rejection;
- fingerprint/runtime substitution rejection;
- serialized RuntimeIdentity substitution rejection;
- digest tamper rejection;
- unknown-field rejection;
- authority-injection rejection;
- upstream LRD-01M, LRD-01N and LRD-01S regression.

The dedicated exact-SHA CI matrix runs on Python 3.11 and 3.14 with frozen dependencies, Ruff, strict MyPy, focused tests, adversarial tests, the complete 01T suite and required upstream revalidation regressions.

## Definition of Done

LRD-01T is closed only when:

1. the implementation is a deterministic one-shot candidate materializer with no discovery/execution authority;
2. exact repository SHA is the single source of `RuntimeIdentity.code_sha`;
3. the resulting snapshot binds a replay-complete RuntimeIdentity and the exact existing LRD-01M fingerprint;
4. all substitution, malformed-input, tamper and authority-injection tests fail closed;
5. focused/adversarial tests, Ruff, strict MyPy and required upstream regressions pass;
6. the complete required pull-request workflow set succeeds on one exact fresh candidate SHA;
7. PR head/base and live `main` are unchanged at the guarded-merge decision;
8. the unchanged validated head is merged;
9. the resulting exact `main` completes the required post-merge validation set successfully;
10. historical `v1.0.1` tag object, target commit and published release remain unchanged;
11. canonical closure evidence is added by a fresh documentation-only closure candidate that itself passes exact-SHA CI, guarded merge and resulting-main validation.

## Canonical closure evidence

Implementation qualification:

- implementation PR: **#249**
- exact implementation candidate SHA: `259d82b18a893ed8a3d7a1b3d50ccf44cc8d3ebe`
- implementation PR base SHA: `27b7416924548d947140920dc2d347dcc4c648f6`
- exact-SHA pull-request workflow qualification: **42/42 SUCCESS**
- guarded implementation merge resulting main: `c25b59cde216b321df86d3441de35d7a9a4b7b2a`
- resulting-main push validation: **38/38 SUCCESS**, 0 queued, 0 in-progress, 0 failure

Immutable release invariant after implementation merge:

- `v1.0.1` tag ref object SHA: `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
- annotated tag target commit: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- release name: `MVROS 1.0.1`
- release target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- invariant result: unchanged

This document is the canonical closure candidate. It may enter `main` only after exact-SHA closure CI and an unchanged head/base guarded merge. The final main push and release invariant are revalidated after that merge; no closure claim relies on an unobserved future result.

## Non-claims

LRD-01T does not discover whether a repository changed, capture mutable Git state, execute replay, acquire fresh environment/provider/storage evidence, preserve artifacts, prove provider durability, prove physical/geographic separation, perform a real disaster-recovery drill, manage keys, select a baseline, modify Product/CCL state, publish a release or certify long-range survivability.

Provider preservation / IDEA-001 remains deferred until **2027-03-09** unless requirements materially change.
