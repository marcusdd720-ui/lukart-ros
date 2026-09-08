# LRD-01B — LongRangeReplayManifestV1 / Replay Capsule V1

Status: implementation contract; authoritative only after exact-SHA CI, guarded merge and
resulting-main validation
Parent program: `continuous LRD-01`
Depends on: `LRD-01A CLOSED / ENGINEERING PASS`
Writable case-history SSOT: Canonical Case Ledger (CCL) only

## 1. Problem

Case Replay v2 proves exact historical case/replay identity, but it is intentionally not a
10+ year execution-closure envelope. LRD-01B adds a separately versioned immutable layer that
binds the long-range identities required by later escrow, Frozen Path, Current Path, crypto
renewal and drift verification without retroactively widening PHX-05 semantics.

The stage does not claim that all referenced bytes already have ten-year physical durability.
`PRESERVED`, `REFERENCE_ONLY` and `UNAVAILABLE` remain explicit and machine-verifiable.

## 2. Authority boundary

Canonical chain:

`Evidence -> CCL -> Case Replay v2 -> LongRangeReplayManifestV1 -> Replay Capsule V1`

- CCL remains the only writable case-history authority.
- Case Replay v2 remains the historical replay identity authority it already was.
- LongRangeReplayManifestV1 binds execution-closure identities; it does not persist Product
  truth or authorize replay results.
- Replay Capsule V1 is an immutable portable evidence envelope, not a case database.
- No manifest/capsule API writes CCL, Gold, policy, trust state, Product state or release state.

## 3. LongRangeReplayManifestV1

Schema: `lukart.long-range-replay-manifest.v1`.

The manifest binds:

- exact `case_id`;
- exact Case Replay v2 manifest identity;
- exact LRD-01A coverage-matrix identity;
- exact Git commit SHA and Git tree SHA;
- a fixed complete v1 artifact-role inventory;
- canonical semantic-result identity;
- optional presentation identity;
- content-derived manifest identity.

The fixed artifact inventory covers:

- Case Replay bundle;
- source archive;
- configuration;
- schemas;
- canonicalization profiles;
- migration registry;
- authorization policy;
- epistemic policy;
- trust policy;
- evidence/input inventory;
- dependency lock;
- dependency set;
- SBOM;
- runtime;
- storage profile;
- crypto profile;
- verification material;
- plugin set;
- provider/model set;
- exact provider request inventory;
- exact provider response inventory;
- renderer;
- semantic result.

Each role has exactly one content-addressed aggregate identity and one preservation state:
`PRESERVED`, `REFERENCE_ONLY` or `UNAVAILABLE`. Missing, duplicate or unknown roles fail
closed. Filename or storage location is never identity.

The manifest itself is content-addressed from canonical bytes. Any material field change,
including one artifact digest, preservation status, code SHA, semantic identity or
presentation identity, changes or invalidates the manifest identity.

## 4. Semantic identity is not presentation identity

`semantic_result_identity` is the canonical semantic comparison boundary. Renderer and
presentation identities remain independently bound so presentation drift is observable but
cannot be misreported as a semantic regression.

Rules:

- same case + same semantic identity + different presentation identity => semantic equality;
- same presentation identity + different semantic identity => semantic mismatch;
- cross-case semantic comparison => fail closed;
- renderer/presentation bytes remain auditable through their own identities.

## 5. Replay assurance semantics

LRD-01B defines evidence-derived assurance levels:

- `EXACT` — complete exact identity/material and deterministic stages reconstructed, with no
  external execution dependency in the verified execution path;
- `VERIFIED_EXTERNAL` — external/provider execution occurred and its exact historical outputs
  were independently verified as the preserved downstream replay inputs; this is explicitly
  **not** a deterministic provider rerun claim;
- `SEMANTIC` — canonical semantic identity was verified but exact deterministic execution was
  not established;
- `UNVERIFIABLE` — required identity or material is incomplete;
- `ABSTAIN` — the available evidence supports neither exact/external nor semantic assurance.

The output level is derived from verification evidence. Callers do not directly choose or
promote an assurance level. External-provider history cannot be promoted to `EXACT` merely
because a historical response was preserved.

## 6. Replay Capsule V1

Schema: `lukart.replay-capsule.v1`.

A capsule embeds the exact canonical LongRangeReplayManifestV1 snapshot and receives its own
content-derived identity.

Published capsules are immutable. Correction is append-only:

`new capsule -> supersedes_digest -> old capsule`

The old capsule remains independently verifiable and audit-accessible. A correction never
rewrites old bytes, historical identities or CCL history. Self-supersession fails closed.

This same lineage pattern is the required model for later replay reports, crypto-renewal
attestations and migration attestations.

## 7. Fail-closed behavior

The v1 parser/validator rejects at least:

- unknown schema or fields;
- unknown artifact role or preservation status;
- missing or duplicate required artifact role;
- malformed Git SHA;
- malformed/unknown content-address algorithm;
- semantic-result identity not matching its bound artifact;
- presentation identity when renderer material is explicitly unavailable;
- manifest identity mismatch;
- capsule identity mismatch;
- cross-case semantic comparison;
- self-supersession.

No compatibility guessing or implicit fallback exists in v1.

## 8. LRD-01A gap handling

LRD-01B does not hide Phase-0 gaps. It gives them an exact representation:

- known identity, bytes physically present => `PRESERVED`;
- known identity, bytes not yet physically escrowed => `REFERENCE_ONLY`;
- known historical dependency but required material unavailable => `UNAVAILABLE`.

Later LRD stages may improve preservation evidence, but they must create a new manifest and,
if published, a new capsule. They may not mutate an existing capsule into a stronger claim.

## 9. Scope deliberately deferred

LRD-01B does **not** implement:

- durable content-addressed artifact escrow backend;
- archive extraction/path/symlink/decompression controls;
- least-privilege network-off execution runner;
- physical Python/runtime reconstruction;
- provider request/response byte capture pipeline;
- Frozen Path execution;
- Current Path execution;
- migration replay engine changes;
- crypto-renewal attestation runtime;
- ongoing LRD health cadence.

Those remain later LRD slices and must not inherit a false PASS from this contract stage.

## 10. Security and long-horizon rationale

The selected envelope architecture is preferred over modifying Case Replay v2 in place because
it preserves historical semantics and makes future migration explicit. A VM/container image
may later be one bound runtime artifact but cannot become the replay authority. A second replay
database is prohibited because it would compete with CCL.

Content identities remain storage-backend independent so future filesystem/object-store/backend
migration cannot silently change artifact identity. The manifest is strict enough that future
schema evolution requires an explicit version/migration rather than permissive interpretation.

## 11. LRD-01B Definition of Done

Engineering closure requires one exact candidate SHA proving:

1. strict LongRangeReplayManifestV1 contract;
2. complete fixed artifact-role inventory;
3. preservation-state binding;
4. exact Case Replay v2 / LRD-01A / Git commit+tree binding;
5. semantic-vs-presentation separation;
6. evidence-derived assurance semantics;
7. immutable Replay Capsule V1 with append-only supersession;
8. focused and adversarial tests including mutation and false-EXACT prevention;
9. Ruff, strict MyPy, full regression, security/policy and exact-SHA CI PASS;
10. guarded unchanged-head merge and resulting-main validation;
11. historical `v1.0.1` baseline and release state unchanged.

LRD-01B engineering PASS does not claim external ten-year durability, offline execution PASS,
provider reproducibility, independent security review or completion of continuous LRD-01.

## 12. Next stage

After LRD-01B closure, the next approved implementation slice is content-addressed Artifact
Escrow plus the least-privilege offline runner boundary. Physical preservation and offline
execution evidence must be proven there rather than inferred from manifest references.
